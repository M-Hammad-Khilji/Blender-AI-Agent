# blender_agent.py
# Runs inside Blender: handles XML-RPC calls and maps safe operations to bpy calls

import sys, argparse, threading, queue, time, os, json

# Try to import bpy — allow this module to be imported outside Blender for
# static analysis or tests. When bpy isn't available we set `bpy = None`
# and make runtime functions raise clear errors if used.
try:
    import bpy
except Exception:
    bpy = None
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

# parse args after -- (Blender passes -- then remaining args to the script)
parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8001)
if "--" in sys.argv:
    idx = sys.argv.index("--") + 1
    args = parser.parse_known_args(sys.argv[idx:])[0]
else:
    # Running outside Blender (tests/dev): use defaults
    args = parser.parse_args([])

HOST = args.host
PORT = args.port
OUTPUT_DIR = "/opt/app/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

task_queue = queue.Queue()
response_queue = queue.Queue()


# Basic primitives (same as before)
def reset_scene():
    if bpy is None:
        raise RuntimeError("bpy not available: reset_scene must run inside Blender")
    bpy.ops.wm.read_homefile(use_empty=True)


def add_box(params):
    name = params.get("name", "Box")
    size = params.get("size", [1, 1, 1])
    location = params.get("location", [0, 0, 0])
    if bpy is None:
        raise RuntimeError("bpy not available: add_box must run inside Blender")
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(location))
    obj = bpy.context.active_object
    obj.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    obj.name = name
    return obj.name


def add_cylinder(params):
    name = params.get("name", "Cyl")
    radius = params.get("radius", 0.5)
    depth = params.get("depth", 1.0)
    location = params.get("location", [0, 0, 0])
    if bpy is None:
        raise RuntimeError("bpy not available: add_cylinder must run inside Blender")
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius, depth=depth, location=tuple(location)
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj.name


def translate(params):
    objname = params.get("object")
    vec = params.get("vector", [0, 0, 0])
    if bpy is None:
        raise RuntimeError("bpy not available: translate must run inside Blender")
    obj = bpy.data.objects.get(objname)
    if not obj:
        return False, "object not found"
    obj.location.x += vec[0]
    obj.location.y += vec[1]
    obj.location.z += vec[2]
    return True, "translated"


def rotate(params):
    objname = params.get("object")
    rot = params.get("rotation", [0, 0, 0])  # radians
    if bpy is None:
        raise RuntimeError("bpy not available: rotate must run inside Blender")
    obj = bpy.data.objects.get(objname)
    if not obj:
        return False, "object not found"
    obj.rotation_euler = tuple(rot)
    return True, "rotated"


def boolean_diff(params):
    target = params.get("target")
    cutter = params.get("cutter")
    if bpy is None:
        raise RuntimeError("bpy not available: boolean_diff must run inside Blender")
    t = bpy.data.objects.get(target)
    c = bpy.data.objects.get(cutter)
    if not t or not c:
        return False, "objects not found"
    mod = t.modifiers.new(name="Bool", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = c
    bpy.context.view_layer.objects.active = t
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(c, do_unlink=True)
    return True, "applied"


def export_obj(params):
    filename = params.get("filename", "model.obj")
    outpath = os.path.join(OUTPUT_DIR, filename)
    if bpy is None:
        raise RuntimeError("bpy not available: export_obj must run inside Blender")
    bpy.ops.export_scene.obj(filepath=outpath, use_selection=False)
    return outpath


# Map op name => function
OP_MAP = {
    "reset": (reset_scene, False),
    "add_box": (add_box, True),
    "add_cylinder": (add_cylinder, True),
    "translate": (translate, True),
    "rotate": (rotate, True),
    "boolean_diff": (boolean_diff, True),
    "export": (export_obj, True),
}


def process_operations_main_thread(ops):
    results = []
    for op in ops.get("operations", []):
        name = op.get("op")
        params = op.get("params", {})
        handler = OP_MAP.get(name)
        if not handler:
            results.append({"op": name, "status": "error", "msg": "unsupported op"})
            continue
        func, returns = handler
        try:
            res = func(params)
            results.append({"op": name, "status": "ok", "result": res})
        except Exception as e:
            results.append({"op": name, "status": "error", "msg": str(e)})
    return results


# Timer function runs in Blender main thread and executes queued tasks
def blender_timer():
    # Drain one item per timer invocation and log progress so we can
    # debug timeouts where the XML-RPC server enqueues work but the
    # Blender main thread doesn't process it.
    if task_queue.empty():
        return 0.3
    item = task_queue.get()
    try:
        print(f"[blender_agent] blender_timer: got item type={item.get('type')}")
        if item.get("type") == "ops":
            ops = item.get("ops")
            print(
                f"[blender_agent] processing ops count={len(ops.get('operations', []))}"
            )
            res = process_operations_main_thread(ops)
            print(
                f"[blender_agent] processed ops, result_len={len(res) if isinstance(res, list) else 1}"
            )
            response_queue.put(res)
        elif item.get("type") == "script":
            script = item.get("script", "")
            print(f"[blender_agent] executing script, len={len(script)}")
            try:
                if bpy is None:
                    raise RuntimeError(
                        "bpy not available: script execution requires Blender"
                    )

                # Provide a small execution environment for scripts. Expose bpy and a helper to render.
                def _render_and_save(filename: str):
                    outpath = os.path.join(OUTPUT_DIR, filename)
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(outpath), exist_ok=True)
                    bpy.context.scene.render.filepath = outpath
                    bpy.ops.render.render(write_still=True)
                    return outpath

                exec_env = {
                    "bpy": bpy,
                    "os": os,
                    "OUTPUT_DIR": OUTPUT_DIR,
                    "render_and_save": _render_and_save,
                }
                # Execute the script in the Blender main thread
                exec(script, exec_env)

                # After execution, ensure we have a preview and export the model
                # Check if script already rendered a preview
                preview_path = None
                exported_files = []

                # Look for any preview files created during script execution
                try:
                    existing_files = os.listdir(OUTPUT_DIR)
                    preview_files = [
                        f
                        for f in existing_files
                        if f.startswith("preview_")
                        and f.endswith((".png", ".jpg", ".jpeg"))
                    ]
                    if preview_files:
                        # Use the most recent preview
                        preview_files.sort(
                            key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)),
                            reverse=True,
                        )
                        preview_path = os.path.join(OUTPUT_DIR, preview_files[0])
                except Exception as e:
                    print(f"[blender_agent] error checking for existing previews: {e}")

                # If no preview was created, generate one
                if not preview_path:
                    fname = f"preview_{int(time.time())}.png"
                    preview_path = _render_and_save(fname)

                # Export the model in common formats
                try:
                    # Export as GLTF (modern, widely supported)
                    gltf_path = os.path.join(
                        OUTPUT_DIR, f"model_{int(time.time())}.gltf"
                    )
                    bpy.ops.export_scene.gltf(filepath=gltf_path, use_selection=False)
                    exported_files.append(os.path.basename(gltf_path))
                    print(f"[blender_agent] exported GLTF: {gltf_path}")
                except Exception as e:
                    print(
                        f"[blender_agent] GLTF export failed (may not be available): {e}"
                    )

                try:
                    # Export as OBJ (legacy, widely supported)
                    obj_path = os.path.join(OUTPUT_DIR, f"model_{int(time.time())}.obj")
                    bpy.ops.export_scene.obj(filepath=obj_path, use_selection=False)
                    exported_files.append(os.path.basename(obj_path))
                    print(f"[blender_agent] exported OBJ: {obj_path}")
                except Exception as e:
                    print(f"[blender_agent] OBJ export failed: {e}")

                print(f"[blender_agent] script executed, preview saved: {preview_path}")
                response_queue.put(
                    {
                        "status": "ok",
                        "preview": preview_path,
                        "exported_files": exported_files,
                    }
                )
            except Exception as e:
                print(f"[blender_agent] exception while executing script: {e}")
                try:
                    response_queue.put({"status": "error", "error": str(e)})
                except Exception:
                    pass
        else:
            print("[blender_agent] unknown item type, ignoring")
            response_queue.put({"error": "unknown item type"})
    except Exception as e:
        print(f"[blender_agent] exception while processing ops: {e}")
        try:
            response_queue.put({"error": str(e)})
        except Exception:
            pass
    return 0.3


bpy.app.timers.register(blender_timer)


# XML-RPC server for requests from Flask
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ("/RPC2",)


def server_thread(host, port):
    server = SimpleXMLRPCServer(
        (host, port), requestHandler=RequestHandler, allow_none=True, logRequests=False
    )
    server.register_introspection_functions()

    def enqueue_ops(ops):
        task_queue.put({"type": "ops", "ops": ops})
        start = time.time()
        while time.time() - start < 60:
            try:
                r = response_queue.get(block=False)
                return r
            except queue.Empty:
                time.sleep(0.05)
        return {"error": "timeout"}

    server.register_function(
        lambda: {"status": "ok", "info": "blender agent alive"}, "ping"
    )
    server.register_function(enqueue_ops, "process_operations")

    def enqueue_script(script_text: str):
        task_queue.put({"type": "script", "script": script_text})
        start = time.time()
        # Allow more time for Blender to perform renders in headless mode
        while time.time() - start < 300:
            try:
                r = response_queue.get(block=False)
                return r
            except queue.Empty:
                time.sleep(0.05)
        return {"error": "timeout"}

    server.register_function(enqueue_script, "process_script")

    print(f"Blender XML-RPC listening on {host}:{port}")
    server.serve_forever()


# Start XML-RPC thread
t = threading.Thread(target=server_thread, args=(HOST, PORT), daemon=True)
t.start()

# Keep process alive
print("Blender agent running. Waiting for tasks...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Shutting down.")

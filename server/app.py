# app.py
import os
import time
import json
from flask import Flask, request, jsonify, send_from_directory
try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("[app] Warning: flask-cors not installed. CORS disabled. Install with: pip install flask-cors")
import xmlrpc.client
import ast
from nebius_client import call_hermes
import requests
import re

BLENDER_RPC_URL = "http://127.0.0.1:8001/RPC2"  # blender_agent XMLRPC
# xmlrpc.client.ServerProxy accepts `allow_none` (lowercase) not `allow_None`
blender_server = xmlrpc.client.ServerProxy(BLENDER_RPC_URL, allow_none=True)


def get_output_dir():
    """Get the output directory path, works both in Docker and locally."""
    output_dir = os.environ.get("OUTPUT_DIR", "/opt/app/output")
    if not os.path.exists(output_dir):
        # Try local output directory
        local_output = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
        if os.path.exists(local_output) or os.path.exists(os.path.dirname(local_output)):
            output_dir = local_output
            os.makedirs(output_dir, exist_ok=True)
        else:
            # Create local output directory
            os.makedirs(local_output, exist_ok=True)
            output_dir = local_output
    return output_dir

# Determine static folder path - works both in Docker and locally
FRONTEND_BUILD = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "build")
if not os.path.exists(FRONTEND_BUILD):
    # Try absolute path for Docker container
    FRONTEND_BUILD = "/opt/app/frontend/build"

app = Flask(__name__, static_folder=FRONTEND_BUILD, static_url_path="/")
# Enable CORS for separate frontend server (if available)
if CORS_AVAILABLE:
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})
else:
    # Add basic CORS headers manually if flask-cors not available
    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:3000')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

# Track the latest preview and generation status so the frontend can poll
LATEST_PREVIEW = {
    "status": "idle",  # idle | running | done | error
    "filename": None,  # basename of the preview file inside the output dir
    "last_updated": None,
    "error": None,
    "exported_files": [],  # List of exported 3D model files
}


# Helper: build a prompt that asks Hermes for structured operations JSON
def build_prompt(user_instruction: str, constraints: dict = None):
    """Return a (system_prompt, user_prompt) pair for Hermes.

    We instruct the model to output a Blender Python script (import bpy
    and use bpy.ops / bpy.data). The user instruction is passed as the
    user prompt. Constraints can be serialized into the system prompt.
    """
    constraints = constraints or {}
    system = (
        "You are an expert Blender Python modeler.\n"
        "Output runnable Blender Python code (starts with `import bpy`).\n"
        "Do NOT include extra commentary or markdown. Only return Python code.\n"
        "\n"
        "IMPORTANT: After creating the 3D model, you should:\n"
        "1. Set up proper lighting and materials for a good preview\n"
        "2. Optionally export the model using bpy.ops.export_scene.gltf() or bpy.ops.export_scene.obj()\n"
        "3. Render a preview image using render_and_save() helper function or bpy.ops.render.render(write_still=True)\n"
        "\n"
        "Example export pattern:\n"
        "  bpy.ops.export_scene.gltf(filepath=os.path.join(OUTPUT_DIR, 'model.gltf'))\n"
        "  render_and_save('preview.png')\n"
    )

    # include any constraints (e.g., polycount, naming conventions) in the system prompt
    if constraints:
        system += "\nCONSTRAINTS:\n" + json.dumps(constraints)

    user = user_instruction
    return system, user


@app.route("/api/generate", methods=["GET", "POST"])
def generate():
    # Determine content type and accept either JSON prompts or raw script bodies
    content_type = (request.content_type or "").lower()
    data = {}
    raw_body = None

    # If user visits this URL in a browser (GET), show usage instructions.
    if request.method == "GET":
        return (
            jsonify(
                {
                    "info": 'POST JSON {"text": "your prompt"} to this endpoint to generate a Blender Python script, or POST raw Blender Python (text/plain) to execute directly.',
                    "example": {
                        "json_prompt": {"text": "Create a small table with four legs"},
                        "raw_script_example": "<send raw .py body as text/plain>",
                    },
                }
            ),
            200,
        )
    # Parse incoming payloads:
    if "application/json" in content_type:
        data = request.get_json(silent=True) or {}
        user_text = data.get("text", "")
        constraints = data.get("constraints", {})
    else:
        # treat other types (text/plain, application/python, etc.) as raw script
        raw_body = request.get_data(as_text=True) or ""
        user_text = ""
        constraints = {}
    if not user_text and not raw_body:
        return jsonify({"error": "no text provided"}), 400

    system_prompt, user_prompt = build_prompt(user_text, constraints)
    model_text = None
    # If the client POSTed a raw script body, use that directly (bypass Nebius)
    if raw_body and raw_body.strip():
        model_text = raw_body
    else:
        # Call Nebius Hermes (returns assistant text containing Blender Python)
        model_text = call_hermes(
            system_prompt, user_prompt, max_tokens=1200, temperature=0.0
        )
    # model_text contains the assistant's Python script
    model_text = model_text or ""
    # Strip common Markdown code fences if the model wrapped the Python in ``` or ```python
    if model_text.strip().startswith("```"):
        # remove first and last triple-fence lines
        parts = model_text.strip().split("\n")
        if parts[0].startswith("```"):
            parts = parts[1:]
        if parts and parts[-1].startswith("```"):
            parts = parts[:-1]
        model_text = "\n".join(parts)

    # Save the raw model script to the shared output directory for inspection
    output_dir = get_output_dir()
    try:
        out_path = os.path.join(output_dir, "last_model_script.py")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(model_text)
        print(f"[app] saved model script to: {out_path}")
    except Exception as e:
        print(f"[app] failed to save model script: {e}")

    # Gentle post-processing to make model-generated renders faster for previews:
    def adjust_for_preview(code: str) -> str:
        # cap Cycles samples to 64
        code = re.sub(
            r"(bpy\.context\.scene\.cycles\.samples\s*=\s*)(\d+)",
            lambda m: m.group(1) + str(min(64, int(m.group(2)))),
            code,
        )
        # cap resolution to 800x800
        code = re.sub(
            r"(bpy\.context\.scene\.render\.resolution_x\s*=\s*)(\d+)",
            lambda m: m.group(1) + str(min(800, int(m.group(2)))),
            code,
        )
        code = re.sub(
            r"(bpy\.context\.scene\.render\.resolution_y\s*=\s*)(\d+)",
            lambda m: m.group(1) + str(min(800, int(m.group(2)))),
            code,
        )
        # Force Eevee for faster previews by replacing CYCLES engine selection
        code = re.sub(
            r"bpy\.context\.scene\.render\.engine\s*=\s*['\"]CYCLES['\"]",
            "bpy.context.scene.render.engine = 'BLENDER_EEVEE'",
            code,
        )
        # Also handle lowercase or other spacing variants
        code = re.sub(
            r"bpy\.context\.scene\.render\.engine\s*=\s*['\"]cycles['\"]",
            "bpy.context.scene.render.engine = 'BLENDER_EEVEE'",
            code,
            flags=re.IGNORECASE,
        )
        return code

    model_text = adjust_for_preview(model_text)

    # Basic AST-based sanitization: reject obviously dangerous constructs
    def sanitize_script(code: str):
        try:
            tree = ast.parse(code)
        except Exception as e:
            return False, f"syntax error during parse: {e}"

        forbidden_calls = set(
            [
                "eval",
                "exec",
                "compile",
                "open",
                "__import__",
                "run",
                "Popen",
                "system",
                "popen",
            ]
        )

        class Scanner(ast.NodeVisitor):
            def __init__(self):
                self.error = None
                # allow only a small set of safe imports used in Blender scripts
                self.allowed_imports = {"bpy", "math", "mathutils", "random"}

            def visit_Import(self, node):
                # only allow imports of names in allowed_imports
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base not in self.allowed_imports:
                        self.error = f"import not allowed: {alias.name}"
                        return

            def visit_ImportFrom(self, node):
                mod = node.module or ""
                base = mod.split(".")[0]
                if base not in self.allowed_imports:
                    self.error = f"from-import not allowed: {mod}"
                    return

            def visit_Call(self, node):
                # collect full name for the called function when possible
                func = node.func
                full = None
                if isinstance(func, ast.Name):
                    full = func.id
                elif isinstance(func, ast.Attribute):
                    # e.g., os.system -> 'os.system'
                    parts = []
                    cur = func
                    while isinstance(cur, ast.Attribute):
                        parts.append(cur.attr)
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        parts.append(cur.id)
                    full = ".".join(reversed(parts))

                if full:
                    for bad in forbidden_calls:
                        if full == bad or full.endswith("." + bad):
                            self.error = f"forbidden call detected: {full}"
                            return

                # continue walking
                self.generic_visit(node)

        scanner = Scanner()
        scanner.visit(ast.parse(code))
        if scanner.error:
            return False, scanner.error
        return True, None

    ok, reason = sanitize_script(model_text)
    if not ok:
        LATEST_PREVIEW.update(
            {"status": "error", "error": reason, "last_updated": int(time.time())}
        )
        return jsonify({"error": "script rejected by sanitizer", "reason": reason}), 400

    # mark generation in progress
    LATEST_PREVIEW.update(
        {"status": "running", "error": None, "last_updated": int(time.time())}
    )
    # Send the raw Python script to the blender agent for execution
    try:
        print("[blender] sending script to blender agent, script_len=", len(model_text))
        resp = blender_server.process_script(model_text)
        print("[blender] response:", resp)
    except Exception as e:
        LATEST_PREVIEW.update(
            {"status": "error", "error": str(e), "last_updated": int(time.time())}
        )
        return (
            jsonify(
                {"error": "failed to send script to blender agent", "details": str(e)}
            ),
            500,
        )

    # Expecting a dict like {"status": "ok", "preview": "/opt/app/output/preview_...png", "exported_files": [...]}
    try:
        if (
            isinstance(resp, dict)
            and resp.get("status") == "ok"
            and resp.get("preview")
        ):
            preview_path = resp.get("preview")
            preview_name = os.path.basename(preview_path)
            exported_files = resp.get("exported_files", [])
            LATEST_PREVIEW.update(
                {
                    "status": "done",
                    "filename": preview_name,
                    "last_updated": int(time.time()),
                    "error": None,
                    "exported_files": exported_files,
                }
            )
            return jsonify(
                {
                    "status": "done",
                    "preview": preview_name,
                    "exported_files": exported_files,
                    "blender_response": resp,
                }
            )
        else:
            # blender returned an error or unexpected shape
            err = resp if resp is not None else "no response"
            LATEST_PREVIEW.update(
                {"status": "error", "error": str(err), "last_updated": int(time.time())}
            )
            return jsonify({"status": "error", "blender_response": resp}), 500
    except Exception as e:
        LATEST_PREVIEW.update(
            {"status": "error", "error": str(e), "last_updated": int(time.time())}
        )
        return (
            jsonify(
                {"error": "failed to interpret blender response", "details": str(e)}
            ),
            500,
        )


@app.route("/api/ping", methods=["GET"])
def ping():
    try:
        return jsonify({"blender": blender_server.ping(), "status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/generate/status", methods=["GET"])
def generate_status():
    """Return the latest preview filename and generation status."""
    return jsonify(LATEST_PREVIEW)


@app.route("/api/preview", methods=["GET"])
def serve_latest_preview():
    """Serve the latest preview image file from the output directory."""
    fname = LATEST_PREVIEW.get("filename")
    if not fname:
        return jsonify({"error": "no preview available"}), 404
    # send_from_directory expects the directory and the filename
    try:
        return send_from_directory(get_output_dir(), fname)
    except Exception as e:
        return jsonify({"error": "failed to read preview", "details": str(e)}), 500


@app.route("/api/preview/<path:filename>", methods=["GET"])
def serve_preview_by_name(filename):
    """Serve a specific preview image by filename from the output directory."""
    try:
        return send_from_directory(get_output_dir(), filename)
    except Exception as e:
        return jsonify({"error": "failed to read preview", "details": str(e)}), 500


@app.route("/api/model/<path:filename>", methods=["GET"])
def serve_model_file(filename):
    """Serve exported 3D model files (GLTF, OBJ, etc.) from the output directory."""
    try:
        return send_from_directory(get_output_dir(), filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": "failed to read model file", "details": str(e)}), 500


@app.route("/api/script/latest", methods=["GET"])
def get_latest_script():
    """Return the contents of last_model_script.py from output for re-execution by the frontend."""
    p = os.path.join(get_output_dir(), "last_model_script.py")
    try:
        with open(p, "r", encoding="utf-8") as fh:
            content = fh.read()
        return content, 200, {"Content-Type": "text/plain; charset=utf-8"}
    except FileNotFoundError:
        return jsonify({"error": "no last_model_script.py found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Serve frontend (if built)
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    # Debug: log static folder location
    static_folder = app.static_folder
    print(f"[serve] static_folder={static_folder}, exists={os.path.exists(static_folder) if static_folder else False}")
    
    # If a built frontend exists, serve its files. Otherwise return a
    # small helpful landing page so visiting :8000/ doesn't produce a
    # confusing generic 404.
    if static_folder and os.path.exists(static_folder):
        if path != "" and os.path.exists(os.path.join(static_folder, path)):
            return send_from_directory(static_folder, path)

        index_path = os.path.join(static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(static_folder, "index.html")

    # Frontend not built / missing — return a minimal HTML page with
    # useful links to the API endpoints for development.
    html = """
        <html>
            <head><title>Blender AI Agent</title></head>
            <body>
                <h1>Blender AI Agent</h1>
                <p>No frontend build found. Use the API endpoints below for development:</p>
                <ul>
                    <li><a href="/api/ping">/api/ping</a> - health check (GET)</li>
                    <li>/api/generate - generate Blender Python (POST JSON: {"text":"your prompt"})</li>
                </ul>
            </body>
        </html>
        """
    return html, 200


@app.route("/api/previews", methods=["GET"])
def list_previews():
    """Return a list of preview image files in the output directory, newest first."""
    outdir = get_output_dir()
    try:
        files = []
        for fn in os.listdir(outdir):
            if fn.lower().endswith((".png", ".jpg", ".jpeg")) and fn.startswith(
                "preview_"
            ):
                full = os.path.join(outdir, fn)
                try:
                    mtime = int(os.path.getmtime(full))
                except Exception:
                    mtime = 0
                files.append({"name": fn, "mtime": mtime})
        files.sort(key=lambda x: x["mtime"], reverse=True)
        return jsonify({"previews": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Flask CLI entry point for running locally
if __name__ == "__main__":
    # For local development
    app.run(host="0.0.0.0", port=8000, debug=True)


@app.route("/dev/poll", methods=["GET"])
def dev_poll_page():
    """A small HTML page demonstrating posting a prompt and polling for preview."""
    html = """
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8" />
            <title>Blender Agent Poll Demo</title>
        </head>
        <body>
            <h2>Blender Agent — Poll Demo</h2>
            <textarea id="prompt" rows="4" cols="60">Create a small wooden table with four legs</textarea><br/>
            <button id="run">Run</button>
            <p id="status">idle</p>
            <img id="preview" src="" style="max-width:400px; border:1px solid #ccc; display:block; margin-top:8px;"/>

            <script>
            async function postPrompt(text){
                document.getElementById('status').innerText='posting...';
                const res = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
                const j = await res.json().catch(()=>null);
                return {status: res.status, body: j};
            }

            async function pollForPreview(){
                const statusEl = document.getElementById('status');
                const preview = document.getElementById('preview');
                const start = Date.now();
                while(true){
                    const r = await fetch('/api/generate/status');
                    const j = await r.json();
                    statusEl.innerText = JSON.stringify(j);
                    if(j.status === 'done' && j.filename){
                        preview.src = '/api/preview';
                        return j.filename;
                    }
                    if(j.status === 'error'){
                        throw new Error(j.error || 'generation error');
                    }
                    if(Date.now() - start > 180000){
                        throw new Error('timeout waiting for preview');
                    }
                    await new Promise(res=>setTimeout(res, 2000));
                }
            }

            document.getElementById('run').addEventListener('click', async ()=>{
                try{
                    const prompt = document.getElementById('prompt').value;
                    const r = await postPrompt(prompt);
                    if(r.status >= 400){
                        document.getElementById('status').innerText = 'server error: '+JSON.stringify(r.body);
                        return;
                    }
                    document.getElementById('status').innerText = 'waiting for preview...';
                    await pollForPreview();
                    document.getElementById('status').innerText = 'done';
                }catch(err){
                    document.getElementById('status').innerText = 'error: '+err.message;
                }
            });
            </script>
        </body>
        </html>
        """
    return html, 200

#!/usr/bin/env bash
set -euo pipefail

echo "[startup] Starting entrypoint"

echo "[startup] Debug: listing /opt/app"
ls -la /opt/app || true

echo "[startup] Debug: listing /opt/app/main (if present)"
ls -la /opt/app/main || true

echo "[startup] Debug: listing /opt/app/blender_agent (if present)"
ls -la /opt/app/blender_agent || true

echo "[startup] Debug: head of blender_agent.py (if present)"
head -n 20 /opt/app/blender_agent/blender_agent.py || true

# Set PYTHONPATH so python can import the app module from /opt/app
export PYTHONPATH="/opt/app/main:/opt/app:${PYTHONPATH:-}"
echo "[startup] PYTHONPATH=$PYTHONPATH"

echo "[startup] Attempting to start Blender (headless)"
# Locate blender_agent script directory under /opt/app
AGENT_DIR=""
if [ -d /opt/app/blender_agent ]; then
	AGENT_DIR=/opt/app/blender_agent
fi

# Start Blender agent in background if binary and script exist
if [ -x /opt/blender/current/blender ] && [ -n "$AGENT_DIR" ] && [ -f "$AGENT_DIR/blender_agent.py" ]; then
	echo "[startup] Found blender_agent at: $AGENT_DIR"
	/opt/blender/current/blender --background --python "$AGENT_DIR/blender_agent.py" -- --host 127.0.0.1 --port 8001 &
	BLENDER_PID=$!
	echo "[startup] Blender launched with PID ${BLENDER_PID}"
else
	echo "[startup] Blender binary or agent script missing; skipping Blender launch"
fi

# give blender a moment to initialize (if it started)
sleep 6

echo "[startup] Starting Flask (Gunicorn) server..."
# Prefer to run from /opt/app/main
if [ -d /opt/app/main ]; then
	cd /opt/app/main || true
else
	cd /opt/app || true
fi

echo "[startup] Working directory: $(pwd)"
exec python3 -m gunicorn --bind 0.0.0.0:8000 app:app --workers 1 --threads 4

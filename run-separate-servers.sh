#!/bin/bash
# Run frontend on port 3000 and Flask API on port 8000
# This is a development setup with separate servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Blender AI Agent - Separate Servers Setup"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating template..."
    cat > .env <<EOF
NEBIUS_API_KEY=
DEV_FALLBACK=0
MODEL_NAME=NousResearch/Hermes-4-70B
EOF
    echo "Please edit .env and add your NEBIUS_API_KEY"
    exit 1
fi

# Source .env
export $(cat .env | grep -v '^#' | xargs)

# Build frontend if needed
if [ ! -f "frontend/build/index.html" ]; then
    echo "Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Install Flask CORS if needed
if ! python3 -c "import flask_cors" 2>/dev/null; then
    echo "Installing flask-cors..."
    pip3 install flask-cors
fi

# Check if Blender is available (for local Blender agent)
BLENDER_CMD="${BLENDER_PATH:-blender}"
if command -v $BLENDER_CMD &> /dev/null; then
    echo "Starting Blender agent..."
    $BLENDER_CMD --background --python "$SCRIPT_DIR/agent/blender_agent.py" -- --host 127.0.0.1 --port 8001 &
    BLENDER_PID=$!
    echo "Blender agent PID: $BLENDER_PID"
    sleep 6
else
    echo "⚠️  Blender not found. Make sure Blender agent is running separately on port 8001"
fi

# Create output directory
mkdir -p output

# Start Flask API server
echo ""
echo "=========================================="
echo "Starting Flask API server on port 8000..."
echo "=========================================="
cd server
export PYTHONPATH="$SCRIPT_DIR/server:$SCRIPT_DIR:$PYTHONPATH"
export OUTPUT_DIR="$SCRIPT_DIR/output"
python3 app.py &
FLASK_PID=$!

# Wait a moment for Flask to start
sleep 3

# Start frontend dev server
echo ""
echo "=========================================="
echo "Starting frontend on port 3000..."
echo "=========================================="
cd "$SCRIPT_DIR/frontend"
REACT_APP_API_URL=http://localhost:8000 npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo "✅ Servers started!"
echo "=========================================="
echo "Frontend: http://localhost:3000"
echo "API:      http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for user interrupt
trap "kill $BLENDER_PID $FLASK_PID $FRONTEND_PID 2>/dev/null || true; exit" INT TERM
wait


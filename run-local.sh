#!/bin/bash
# Run Blender AI Agent locally without Docker
# This script starts both the Blender agent and Flask server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Blender AI Agent - Local Setup"
echo "=========================================="

# Check if Blender is installed
if ! command -v blender &> /dev/null; then
    echo "⚠️  Blender not found in PATH"
    echo "Please install Blender or add it to your PATH"
    echo "Or set BLENDER_PATH environment variable"
    exit 1
fi

BLENDER_PATH="${BLENDER_PATH:-blender}"
echo "Using Blender: $BLENDER_PATH"

# Check if frontend is built
if [ ! -f "frontend/build/index.html" ]; then
    echo "⚠️  Frontend not built. Building now..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Set environment variables
export DEV_FALLBACK="${DEV_FALLBACK:-1}"
export NEBIUS_API_KEY="${NEBIUS_API_KEY:-}"
export PYTHONPATH="$SCRIPT_DIR/server:$SCRIPT_DIR:$PYTHONPATH"

# Create output directory
mkdir -p output

echo ""
echo "Starting Blender agent in background..."
# Start Blender agent
$BLENDER_PATH --background --python "$SCRIPT_DIR/agent/blender_agent.py" -- --host 127.0.0.1 --port 8001 &
BLENDER_PID=$!
echo "Blender agent started with PID: $BLENDER_PID"

# Wait for Blender to initialize
echo "Waiting for Blender to initialize (6 seconds)..."
sleep 6

echo ""
echo "Starting Flask server..."
echo "Access the app at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers"

# Start Flask (using development server)
cd server
python3 -m flask run --host=0.0.0.0 --port=8000 --reload

# Cleanup on exit
trap "kill $BLENDER_PID 2>/dev/null || true" EXIT


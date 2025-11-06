#!/bin/bash
set -euo pipefail

# Build and run Blender AI Agent with GPU
# Requirements: Docker Desktop with NVIDIA GPU support (WSL2 + NVIDIA Container Toolkit)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  cat <<EOF > .env
NEBIUS_API_KEY=
DEV_FALLBACK=0
MODEL_NAME=NousResearch/Hermes-4-70B
EOF
  echo "Created .env. Edit NEBIUS_API_KEY before continuing."
  exit 1
fi

# Ensure frontend is built so Flask can serve it
if [ ! -f frontend/build/index.html ]; then
  echo "Frontend build not found. Building now..."
  (cd frontend && npm install && npm run build)
fi

mkdir -p output

echo "Rebuilding images with --no-cache..."
docker-compose build --no-cache

echo "Starting stack with GPU..."
docker-compose up -d

echo "Showing status..."
docker-compose ps

echo "Follow logs with: docker-compose logs -f"
echo "Open http://localhost:8000"

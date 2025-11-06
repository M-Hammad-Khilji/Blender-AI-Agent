#!/bin/bash
# Rebuild Docker container with --no-cache to ensure frontend build is included

echo "Stopping any running containers..."
docker-compose down 2>/dev/null || true

echo "Rebuilding Docker image with --no-cache..."
docker-compose build --no-cache

echo "Starting container..."
docker-compose up -d

echo "Checking container status..."
docker-compose ps

echo ""
echo "Container should be running. Check logs with:"
echo "  docker-compose logs -f"
echo ""
echo "Access the app at: http://localhost:8000"


# Quick Start Guide

## Option 1: Docker (Recommended - Everything on Port 8000)

```bash
# 1. Create .env file with your Nebius API key
echo "NEBIUS_API_KEY=your_key_here" > .env
echo "DEV_FALLBACK=0" >> .env

# 2. Build frontend
cd frontend && npm install && npm run build && cd ..

# 3. Clean and rebuild Docker
docker-compose down --remove-orphans
docker-compose build --no-cache
docker-compose up

# 4. Access at http://localhost:8000
```

## Option 2: Separate Servers (Frontend on 3000, API on 8000)

```bash
# 1. Create .env file
echo "NEBIUS_API_KEY=your_key_here" > .env

# 2. Install dependencies
pip3 install flask flask-cors requests
cd frontend && npm install && cd ..

# 3. Run the helper script
chmod +x run-separate-servers.sh
./run-separate-servers.sh
```

This will:
- Start Flask API on **http://localhost:8000**
- Start React dev server on **http://localhost:3000**
- Frontend will automatically connect to API on port 8000

## Troubleshooting Port 8000 Not Responding

### Check if container is running:
```bash
docker-compose ps
docker-compose logs -f
```

### Check if Flask is running locally:
```bash
curl http://localhost:8000/api/ping
```

### Verify frontend build exists:
```bash
ls -la frontend/build/index.html
```

### If using separate servers, check both:
```bash
# Terminal 1: Flask API
cd server
python3 app.py

# Terminal 2: Frontend
cd frontend
REACT_APP_API_URL=http://localhost:8000 npm run dev
```

Then access: **http://localhost:3000**


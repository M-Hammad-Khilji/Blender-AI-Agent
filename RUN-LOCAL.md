# Running Blender AI Agent Without Docker

If you can't use Docker Desktop, you can run the application locally.

## Prerequisites

1. **Blender 4.2+** installed and in your PATH
   - Download from: https://www.blender.org/download/
   - Or set `BLENDER_PATH` environment variable to your Blender executable

2. **Python 3.8+** with pip

3. **Node.js and npm** (for frontend build)

## Setup Steps

### 1. Build the Frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Install Python Dependencies

```bash
pip install flask requests
# Or if using system Python:
pip3 install flask requests
```

### 3. Set Environment Variables (Optional)

```bash
# For local testing without Nebius API:
export DEV_FALLBACK=1

# Or if you have Nebius API key:
export NEBIUS_API_KEY=your_key_here
```

### 4. Run the Application

**Option A: Use the run script (recommended)**

```bash
chmod +x run-local.sh
./run-local.sh
```

**Option B: Manual steps**

Terminal 1 - Start Blender Agent:
```bash
blender --background --python agent/blender_agent.py -- --host 127.0.0.1 --port 8001
```

Terminal 2 - Start Flask Server:
```bash
cd server
python3 app.py
# Or: python3 -m flask run --host=0.0.0.0 --port=8000
```

### 5. Access the Application

Open your browser to: **http://localhost:8000**

## Troubleshooting

### Blender not found
- Make sure Blender is installed and in your PATH
- Or set: `export BLENDER_PATH=/path/to/blender`

### Port 8000 already in use
- Change the port in `server/app.py` or use: `python3 -m flask run --port=8001`

### Frontend not loading
- Make sure `frontend/build` directory exists
- Check that `frontend/build/index.html` exists

### Blender agent not responding
- Check that Blender agent is running on port 8001
- Check logs in Terminal 1 where Blender is running

## Output Files

Generated models and previews will be saved to: `./output/`

## Notes

- The Blender agent must be running before starting Flask
- Both processes need to be running simultaneously
- Use `Ctrl+C` to stop either process


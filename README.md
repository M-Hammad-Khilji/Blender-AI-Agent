# 🎨 Blender AI Agent

An AI-powered 3D model generator that uses natural language to create Blender Python scripts and generate 3D models automatically.

## Features

- ✨ **Natural Language Input**: Describe your 3D model in plain English
- 🤖 **AI-Powered Generation**: Uses LLM (Hermes-4-70B via Nebius) to generate Blender Python scripts
- 🎨 **Automatic Rendering**: Generates preview images and exports models in GLTF/OBJ formats
- 📊 **Real-time Updates**: Live status updates and periodic preview polling
- 🎯 **Beautiful UI**: Modern, responsive interface for easy interaction

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- (Optional) Nebius API key for LLM access (or use DEV_FALLBACK=1 for testing)

### Setup

1. **Clone and navigate to the project:**
   ```bash
   cd Blender-AI-Agent
   ```

2. **Set up environment variables** (optional):
   ```bash
   # Create .env file (or set environment variables)
   export NEBIUS_API_KEY=your_api_key_here
   # Or for local testing without API:
   export DEV_FALLBACK=1
   ```

3. **Build the frontend:**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

4. **Build and run with Docker Compose:**
   ```bash
   # Create output directory
   mkdir -p output
   
   # Build and run
   docker-compose up --build
   ```

   Or build manually:
   ```bash
   docker build --build-arg BLENDER_VER=4.2.14 -t blender-ai-agent:latest .
   docker run --rm -it -p 8000:8000 -v $(pwd)/output:/opt/app/output blender-ai-agent:latest
   ```

5. **Access the UI:**
   - Open your browser to: `http://localhost:8000`
   - Enter a prompt like: "Create a small wooden table with four legs"
   - Click "Generate" and wait for your 3D model!

## Usage Examples

Try these prompts:
- "Create a small wooden table with four legs and a simple brown material"
- "Make a comfortable chair for computer geeks with ergonomic back support"
- "Design a modern lamp with a geometric base"
- "Build a simple bookshelf with three shelves"

## Project Structure

```
Blender-AI-Agent/
├── agent/              # Blender agent (runs inside Blender)
│   └── blender_agent.py
├── server/             # Flask backend
│   ├── app.py          # Main API server
│   ├── nebius_client.py # LLM client
│   └── startup.sh      # Container startup script
├── frontend/           # React frontend
│   └── src/
│       └── App.jsx     # Main UI component
├── output/             # Generated models and previews
├── Dockerfile          # Container definition
└── docker-compose.yml  # Docker Compose configuration
```

## API Endpoints

- `POST /api/generate` - Generate a 3D model from text prompt
- `GET /api/generate/status` - Get current generation status
- `GET /api/preview` - Get latest preview image
- `GET /api/preview/<filename>` - Get specific preview
- `GET /api/model/<filename>` - Download exported 3D model (GLTF/OBJ)
- `GET /api/script/latest` - View generated Blender Python script
- `GET /api/ping` - Health check

## How It Works

1. **User Input**: User provides a natural language description
2. **LLM Generation**: The prompt is sent to the LLM (Nebius Hermes) which generates Blender Python code
3. **Script Execution**: The generated script is executed inside a Blender instance
4. **Model Export**: Blender exports the model in GLTF and OBJ formats
5. **Preview Rendering**: A preview image is rendered and displayed
6. **User Download**: User can download the 3D model files

## Development

### Running Locally (without Docker)

1. Install Blender 4.2+ manually
2. Install Python dependencies:
   ```bash
   pip install flask gunicorn requests
   ```
3. Run the Blender agent:
   ```bash
   blender --background --python agent/blender_agent.py -- --host 127.0.0.1 --port 8001
   ```
4. Run the Flask server:
   ```bash
   cd server
   python app.py
   ```
5. Serve the frontend (built):
   ```bash
   cd frontend/build
   python -m http.server 3000
   ```

### Testing

```bash
# Test the API
python server/test_client_nl.py

# Or use curl
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Create a cube"}'
```

## Troubleshooting

- **Blender agent not responding**: Check if Blender is running and XML-RPC is accessible on port 8001
- **No preview generated**: Ensure Blender has proper rendering setup (Eevee engine)
- **Export fails**: Some Blender versions may not have GLTF exporter - OBJ will still work
- **Frontend not loading**: Make sure `frontend/build` directory exists and was built

## License

Check your repository license.

## Contributing

Contributions welcome! Please ensure code follows existing patterns and includes tests where applicable.

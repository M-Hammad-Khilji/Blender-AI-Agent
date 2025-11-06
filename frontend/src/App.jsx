import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

// Configure API base URL - use port 8000 for Flask API
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
axios.defaults.baseURL = API_BASE_URL;

export default function App() {
  const [text, setText] = useState("Create a small wooden table with four legs and a simple brown material");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState(null);
  const [previewHistory, setPreviewHistory] = useState([]);
  const [generatedScript, setGeneratedScript] = useState(null);
  const [exportedFiles, setExportedFiles] = useState([]);
  const mounted = useRef(true);
  const pollIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      mounted.current = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Periodic preview polling during generation
  useEffect(() => {
    if (status === 'running' || status === 'queued') {
      pollIntervalRef.current = setInterval(async () => {
        try {
          const r = await axios.get('/api/generate/status');
          const j = r.data;
          if (j.status === 'done' && j.filename) {
            setPreviewUrl('/api/preview?' + Date.now());
            setStatus('done');
            setPolling(false);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            // Load preview history and exported files
            const previews = await listPreviews();
            setPreviewHistory(previews.slice(0, 5)); // Keep last 5
            if (j.exported_files) {
              setExportedFiles(j.exported_files);
            }
          } else if (j.status === 'error') {
            setError(j.error || JSON.stringify(j));
            setStatus('error');
            setPolling(false);
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          } else {
            setStatus(j.status || 'running');
            // Try to load any available previews during generation
            if (j.filename) {
              setPreviewUrl('/api/preview?' + Date.now());
            }
          }
        } catch (e) {
          console.error('Poll error:', e);
        }
      }, 2000); // Poll every 2 seconds
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [status]);

  async function pollStatus(timeoutMs = 180000) {
    const start = Date.now();
    setPolling(true);
    setStatus('running');
    try {
      while (Date.now() - start < timeoutMs) {
        const r = await axios.get('/api/generate/status');
        const j = r.data;
        setStatus(j.status || 'running');
        if (j.status === 'done' && j.filename) {
          setPreviewUrl('/api/preview?' + Date.now());
          setResult(j);
          setPolling(false);
          // Load preview history and exported files
          const previews = await listPreviews();
          setPreviewHistory(previews.slice(0, 5));
          if (j.exported_files) {
            setExportedFiles(j.exported_files);
          }
          return j;
        }
        if (j.status === 'error') {
          setError(j.error || JSON.stringify(j));
          setPolling(false);
          return j;
        }
        await new Promise(res => setTimeout(res, 2000));
      }
      setError('timeout waiting for preview');
      setPolling(false);
      return null;
    } catch (e) {
      setError(e.message || String(e));
      setPolling(false);
      return null;
    }
  }

  const submit = async () => {
    setError(null);
    setResult(null);
    setPreviewUrl(null);
    setPreviewHistory([]);
    setGeneratedScript(null);
    setExportedFiles([]);
    setStatus('sending');
    try {
      const r = await axios.post('/api/generate', { text }, { timeout: 120000 });
      setResult(r.data);
      setStatus('queued');
      // Load generated script and exported files
      try {
        const scriptRes = await axios.get('/api/script/latest', { responseType: 'text' });
        setGeneratedScript(scriptRes.data);
      } catch (e) {
        console.warn('Could not load script:', e);
      }
      if (r.data.exported_files) {
        setExportedFiles(r.data.exported_files);
      }
      await pollStatus();
    } catch (e) {
      setError(e.response?.data?.error || e.message || String(e));
      setStatus('error');
    }
  };

  const runLatestScript = async () => {
    setError(null);
    setResult(null);
    setPreviewUrl(null);
    setPreviewHistory([]);
    setStatus('sending-latest');
    try {
      const s = await axios.get('/api/script/latest', { responseType: 'text' });
      setGeneratedScript(s.data);
      await axios.post('/api/generate', s.data, { headers: { 'Content-Type': 'text/plain' }, timeout: 300000 });
      setStatus('queued-latest');
      await pollStatus(300000);
    } catch (e) {
      setError(e.response?.data?.error || e.message || String(e));
      setStatus('error');
    }
  }

  const listPreviews = async () => {
    try {
      const r = await axios.get('/api/previews');
      return r.data.previews || [];
    } catch (e) {
      return [];
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'done': return '#4caf50';
      case 'error': return '#f44336';
      case 'running': case 'queued': case 'sending': return '#2196f3';
      default: return '#757575';
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'idle': return 'Ready';
      case 'sending': return 'Sending to LLM...';
      case 'queued': return 'Queued for Blender...';
      case 'running': return 'Generating 3D model...';
      case 'done': return 'Complete!';
      case 'error': return 'Error';
      default: return status;
    }
  }

  return (
    <div style={{
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif",
      padding: 0,
      margin: 0,
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <div style={{
        maxWidth: 1400,
        margin: '0 auto',
        padding: '20px',
        background: 'rgba(255, 255, 255, 0.95)',
        minHeight: '100vh',
        boxShadow: '0 0 40px rgba(0,0,0,0.1)'
      }}>
        <header style={{ marginBottom: 30, textAlign: 'center', borderBottom: '2px solid #667eea', paddingBottom: 20 }}>
          <h1 style={{
            margin: 0,
            fontSize: '2.5em',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontWeight: 'bold'
          }}>
            🎨 Blender AI Designer
          </h1>
          <p style={{ color: '#666', marginTop: 10, fontSize: '1.1em' }}>
            Generate 3D models with natural language using AI
          </p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 30, marginBottom: 30 }}>
          {/* Left Panel - Input */}
          <div style={{
            background: '#fff',
            padding: 25,
            borderRadius: 12,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ marginTop: 0, color: '#333', fontSize: '1.5em' }}>Describe Your 3D Model</h2>
            <textarea
              rows={8}
              style={{
                width: "100%",
                padding: 12,
                fontSize: '1em',
                border: '2px solid #e0e0e0',
                borderRadius: 8,
                fontFamily: 'inherit',
                resize: 'vertical',
                boxSizing: 'border-box'
              }}
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Example: Create a comfortable chair for computer geeks with ergonomic back support and armrests"
            />
            <div style={{ marginTop: 15, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button
                onClick={submit}
                disabled={status === 'running' || status === 'sending' || status === 'queued'}
                style={{
                  padding: "12px 24px",
                  fontSize: '1em',
                  background: status === 'running' || status === 'sending' || status === 'queued' ? '#ccc' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 8,
                  cursor: status === 'running' || status === 'sending' || status === 'queued' ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                  transition: 'transform 0.2s',
                }}
                onMouseOver={(e) => {
                  if (status !== 'running' && status !== 'sending' && status !== 'queued') {
                    e.target.style.transform = 'scale(1.05)';
                  }
                }}
                onMouseOut={(e) => {
                  e.target.style.transform = 'scale(1)';
                }}
              >
                {status === 'running' || status === 'sending' || status === 'queued' ? '⏳ Generating...' : '✨ Generate'}
              </button>
              <button
                onClick={runLatestScript}
                disabled={status === 'running' || status === 'sending' || status === 'queued'}
                style={{
                  padding: "12px 24px",
                  fontSize: '1em',
                  background: status === 'running' || status === 'sending' || status === 'queued' ? '#ccc' : '#f5f5f5',
                  color: '#333',
                  border: '2px solid #e0e0e0',
                  borderRadius: 8,
                  cursor: status === 'running' || status === 'sending' || status === 'queued' ? 'not-allowed' : 'pointer',
                  fontWeight: '500'
                }}
              >
                🔄 Re-run Latest
              </button>
            </div>

            {/* Status Indicator */}
            <div style={{ marginTop: 20, padding: 15, background: '#f8f9fa', borderRadius: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  background: getStatusColor(),
                  boxShadow: (status === 'running' || status === 'queued') ? `0 0 10px ${getStatusColor()}` : 'none',
                  animation: (status === 'running' || status === 'queued') ? 'pulse 2s infinite' : 'none'
                }}></div>
                <strong style={{ color: '#333' }}>Status:</strong>
                <span style={{ color: getStatusColor(), fontWeight: '500' }}>{getStatusText()}</span>
                {polling && <span style={{ color: '#666', fontSize: '0.9em' }}> (polling...)</span>}
              </div>
              {error && (
                <div style={{
                  marginTop: 10,
                  padding: 10,
                  background: '#ffebee',
                  border: '1px solid #f44336',
                  borderRadius: 6,
                  color: '#c62828',
                  fontSize: '0.9em'
                }}>
                  <strong>Error:</strong> {typeof error === 'string' ? error : JSON.stringify(error)}
                </div>
              )}
            </div>

            {/* Generated Script Preview */}
            {generatedScript && (
              <div style={{ marginTop: 20 }}>
                <details style={{ background: '#f8f9fa', padding: 15, borderRadius: 8 }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#333', marginBottom: 10 }}>
                    📝 Generated Blender Script (Click to view)
                  </summary>
                  <pre style={{
                    maxHeight: 300,
                    overflow: 'auto',
                    background: '#fff',
                    padding: 15,
                    borderRadius: 6,
                    fontSize: '0.85em',
                    border: '1px solid #e0e0e0',
                    marginTop: 10
                  }}>
                    {generatedScript}
                  </pre>
                </details>
              </div>
            )}
          </div>

          {/* Right Panel - Preview */}
          <div style={{
            background: '#fff',
            padding: 25,
            borderRadius: 12,
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ marginTop: 0, color: '#333', fontSize: '1.5em' }}>3D Model Preview</h2>
            <div style={{
              width: "100%",
              minHeight: 400,
              border: '2px dashed #e0e0e0',
              borderRadius: 12,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: status === 'running' || status === 'queued' ? 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)' : '#f8f9fa',
              position: 'relative',
              overflow: 'hidden'
            }}>
              {previewUrl ? (
                <img
                  alt="3D model preview"
                  src={previewUrl}
                  style={{
                    maxWidth: '100%',
                    maxHeight: 400,
                    borderRadius: 8,
                    boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                  }}
                />
              ) : (
                <div style={{
                  color: '#999',
                  textAlign: 'center',
                  padding: 40
                }}>
                  <div style={{ fontSize: '4em', marginBottom: 20 }}>🎨</div>
                  <div style={{ fontSize: '1.1em' }}>
                    {status === 'running' || status === 'queued' ? 'Generating your 3D model...' : 'No preview yet'}
                  </div>
                  {(status === 'running' || status === 'queued') && (
                    <div style={{ marginTop: 20, fontSize: '0.9em', color: '#666' }}>
                      This may take 30-60 seconds...
                    </div>
                  )}
                </div>
              )}
              {(status === 'running' || status === 'queued') && (
                <div style={{
                  position: 'absolute',
                  top: 10,
                  right: 10,
                  background: 'rgba(102, 126, 234, 0.9)',
                  color: 'white',
                  padding: '8px 16px',
                  borderRadius: 20,
                  fontSize: '0.85em',
                  fontWeight: 'bold',
                  animation: 'pulse 2s infinite'
                }}>
                  ⚡ Generating...
                </div>
              )}
            </div>
            <div style={{ marginTop: 15, fontSize: '0.9em', color: '#666' }}>
              {previewUrl ? '✨ Your 3D model has been generated!' : 'Preview will appear here once generation completes.'}
            </div>

            {/* Download Model Files */}
            {exportedFiles.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3 style={{ fontSize: '1em', color: '#333', marginBottom: 10 }}>📦 Download 3D Model</h3>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {exportedFiles.map((filename, idx) => (
                    <a
                      key={idx}
                      href={`/api/model/${filename}`}
                      download={filename}
                      style={{
                        display: 'inline-block',
                        padding: '8px 16px',
                        background: '#667eea',
                        color: 'white',
                        textDecoration: 'none',
                        borderRadius: 6,
                        fontSize: '0.9em',
                        fontWeight: '500',
                        transition: 'background 0.2s'
                      }}
                      onMouseOver={(e) => e.target.style.background = '#764ba2'}
                      onMouseOut={(e) => e.target.style.background = '#667eea'}
                    >
                      📥 {filename}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Preview History */}
            {previewHistory.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <h3 style={{ fontSize: '1em', color: '#333', marginBottom: 10 }}>Recent Previews</h3>
                <div style={{ display: 'flex', gap: 10, overflowX: 'auto' }}>
                  {previewHistory.map((p, idx) => (
                    <img
                      key={idx}
                      src={`/api/preview/${p.name}`}
                      alt={`Preview ${idx + 1}`}
                      style={{
                        width: 80,
                        height: 80,
                        objectFit: 'cover',
                        borderRadius: 6,
                        border: '2px solid #e0e0e0',
                        cursor: 'pointer'
                      }}
                      onClick={() => setPreviewUrl(`/api/preview/${p.name}`)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          marginTop: 30,
          padding: 20,
          background: '#f8f9fa',
          borderRadius: 12,
          textAlign: 'center',
          color: '#666',
          fontSize: '0.9em'
        }}>
          <p style={{ margin: 0 }}>
            Powered by Blender AI Agent • Generate 3D models with natural language
          </p>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

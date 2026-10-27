import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

class GlobalErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("GlobalErrorBoundary caught an error:", error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          backgroundColor: '#0f172a',
          color: '#f8fafc',
          padding: '40px 24px',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{ maxWidth: 800, margin: '0 auto', background: '#1e293b', borderRadius: 16, border: '1px solid #334155', padding: 32 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <span style={{ fontSize: 24 }}>⚠️</span>
              <h1 style={{ fontSize: 20, fontWeight: 'bold', color: '#f43f5e', margin: 0 }}>
                UI Runtime Error
              </h1>
            </div>
            <p style={{ color: '#cbd5e1', fontSize: 14, marginBottom: 20 }}>
              An error occurred during page rendering:
            </p>
            <pre style={{
              background: '#0f172a',
              border: '1px solid #475569',
              borderRadius: 8,
              padding: 16,
              color: '#fca5a5',
              fontSize: 13,
              overflowX: 'auto',
              whiteSpace: 'pre-wrap'
            }}>
              {this.state.error?.toString()}
            </pre>
            {this.state.errorInfo?.componentStack && (
              <pre style={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 8,
                padding: 16,
                color: '#94a3b8',
                fontSize: 11,
                overflowX: 'auto',
                marginTop: 12
              }}>
                {this.state.errorInfo.componentStack}
              </pre>
            )}
            <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
              <button
                onClick={() => window.location.reload()}
                style={{
                  background: '#6366f1',
                  color: 'white',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Reload Page
              </button>
              <button
                onClick={() => { localStorage.clear(); window.location.href = '/'; }}
                style={{
                  background: '#334155',
                  color: '#cbd5e1',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Reset Session & Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <GlobalErrorBoundary>
      <App />
    </GlobalErrorBoundary>
  </React.StrictMode>
);

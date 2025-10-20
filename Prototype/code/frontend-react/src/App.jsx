import { useState } from 'react'
import axios from 'axios'
import Dashboard from './components/Dashboard'
import './App.css'


function App() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [usingDemo, setUsingDemo] = useState(false)

  const loadDemoData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await axios.get('http://localhost:5001/api/demo-data')
      setData(response.data)
      setUsingDemo(true)
    } catch (err) {
      setError('Failed to load demo data: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    setLoading(true)
    setError(null)
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await axios.post('http://localhost:5001/api/upload', formData)
      setData(response.data)
      setUsingDemo(false)
    } catch (err) {
      setError('Failed to upload file: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const triggerFileUpload = () => {
    document.getElementById('file-upload').click()
  }

  const clearDemoData = () => {
    setData(null)
    setUsingDemo(false)
  }

  return (
    <div className="app-container">
      {!data ? (
        <div className="landing-page">
          {/* Brand Logo */}
          <div className="brand">ContinuumAI</div>
          
          {/* Navigation */}
          <div className="navbar">
            <a href="#">login</a>
            <a href="#">signup</a>
          </div>

          {/* Hero Section */}
          <div className="hero">
            <div className="hero-left">
              <h1>Discover powerful insights with <span className="gradient-text">ContinuumAI</span></h1>
              <p>Your AI analytics partner — elegant, insightful, and effortless.</p>
              
              <div className="button-group">
                <input 
                  id="file-upload"
                  type="file" 
                  accept=".csv"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                />
                <button 
                  className="upload-btn custom-btn" 
                  onClick={triggerFileUpload}
                  disabled={loading}
                >
                  {loading ? 'Loading...' : 'Upload CSV'}
                </button>
                <button 
                  className="demo-btn custom-btn" 
                  onClick={loadDemoData}
                  disabled={loading}
                >
                  {loading ? 'Loading...' : 'Use Demo Data'}
                </button>
              </div>

              {error && <div className="error-message">{error}</div>}
            </div>
            <div className="hero-right"></div>
          </div>

          {/* Footer */}
          <div className="footer">ContinuumAI © 2025 — The Future of Business Intelligence</div>
        </div>
      ) : (
        <Dashboard data={data} usingDemo={usingDemo} onClearDemo={clearDemoData} />
      )}
    </div>
  )
}

export default App
import './App.css'
import { useState, useEffect } from 'react';
import { streamHandleEmail, register, login, logoutAll, getSessionHealthSnapshot } from './api';
import InputForm from './components/inputForm/InputForm';
import OutputDisplay from './components/outputDisplay/OutputDisplay';
import AuthPanel from './components/auth/AuthPanel';
import Toast from './components/ui/Toast';

function App() {
  const [streamingText, setStreamingText] = useState('');
  const [completedResponse, setCompletedResponse] = useState<unknown | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const [currentUser, setCurrentUser] = useState<string | null>(localStorage.getItem('username'));
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [sessionHealth, setSessionHealth] = useState(getSessionHealthSnapshot());

  const refreshSessionHealth = () => {
    setSessionHealth(getSessionHealthSnapshot())
  }

  const handleSubmit = async (emailText: string) => {
    setStreamingText('');
    setCompletedResponse(null);
    setError('');
    setIsLoading(true);

    await streamHandleEmail(
      emailText,
      (delta) => {
        setStreamingText((prev) => prev + delta);
      },
      (response) => {
        setCompletedResponse(response);
        setIsLoading(false);
      },
      (errorMsg) => {
        setError(errorMsg);
        setIsLoading(false);
      }
    );
  };

  const handleRegister = async (username: string, email: string, password: string) => {
    setError('')
    try {
      const body = await register(username, email, password)
      if (body.access_token) {
        localStorage.setItem('access_token', body.access_token)
        localStorage.setItem('refresh_token', body.refresh_token)
        localStorage.setItem('username', body.user.username)
        // clear any previous responses when a new user signs in
        setStreamingText('')
        setCompletedResponse(null)
        setError('')
        setCurrentUser(body.user.username)
        refreshSessionHealth()
      } else if (body.detail) {
        setError(body.detail)
      }
    } catch (e) {
      setError(String(e))
    }
  }

  const handleLogin = async (username: string, password: string) => {
    setError('')
    try {
      const body = await login(username, password)
      if (body.access_token) {
        localStorage.setItem('access_token', body.access_token)
        localStorage.setItem('refresh_token', body.refresh_token)
        localStorage.setItem('username', body.user.username)
        // clear any previous responses when a user signs in
        setStreamingText('')
        setCompletedResponse(null)
        setError('')
        setCurrentUser(body.user.username)
        refreshSessionHealth()
      } else if (body.detail) {
        setError(body.detail)
      }
    } catch (e) {
      setError(String(e))
    }
  }

  const handleLogoutAll = async () => {
    setError('')
    try {
      await logoutAll()
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('username')
      // clear UI state on logout
      setStreamingText('')
      setCompletedResponse(null)
      setError('')
      setCurrentUser(null)
      refreshSessionHealth()
    } catch (e) {
      setError(String(e))
    }
  }

  useEffect(() => {
    const onLoggedOut = () => {
      // clear UI and local tokens when refresh failed or server forced logout
      setStreamingText('')
      setCompletedResponse(null)
      setError('')
      setCurrentUser(null)
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('username')
      setToastMessage('Session expired or invalid. Please sign in again.')
      refreshSessionHealth()
    }
    window.addEventListener('auth:logged_out', onLoggedOut)
    return () => window.removeEventListener('auth:logged_out', onLoggedOut)
  }, [])

  useEffect(() => {
    refreshSessionHealth()
    const id = window.setInterval(() => {
      refreshSessionHealth()
    }, 15000)
    return () => window.clearInterval(id)
  }, [currentUser])


  return (
    <div className="app-container">
      <div className="app-header">
        <h1>🤖 Support Ticket MVP</h1>
        <p>Real-time AI-powered support ticket handling with streaming responses</p>
      </div>

      {!currentUser ? (
        <AuthPanel onRegister={handleRegister} onLogin={handleLogin} error={error} />
      ) : (
        <div className="app-content">
          <div className="signed-in-bar">
            <div className="signed-in-left">
              <div>Signed in as <strong>{currentUser}</strong></div>
              <div
                className={`session-health-badge session-${sessionHealth.status}`}
                aria-label="session-health"
              >
                Session: {sessionHealth.label}
                {sessionHealth.secondsRemaining !== null && sessionHealth.secondsRemaining >= 0 && (
                  <span className="session-seconds"> ({sessionHealth.secondsRemaining}s)</span>
                )}
              </div>
            </div>
            <button onClick={handleLogoutAll}>Logout All Devices</button>
          </div>
          <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
          <OutputDisplay 
            streamingText={streamingText}
            completedResponse={completedResponse}
            error={error}
            isStreaming={isLoading}
          />
        </div>
      )}
      {toastMessage && (
        <Toast message={toastMessage} onClose={() => setToastMessage(null)} />
      )}
    </div>
  )
}

export default App


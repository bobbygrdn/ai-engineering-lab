import { useState } from 'react'

type Props = {
  onRegister: (u: string, e: string, p: string) => Promise<void>
  onLogin: (u: string, p: string) => Promise<void>
  error?: string
}

export default function AuthPanel({ onRegister, onLogin, error }: Props) {
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const validateRegister = () => {
    if (username.length < 3) return 'Username must be at least 3 characters'
    if (!email.includes('@')) return 'Enter a valid email address'
    if (password.length < 10) return 'Password must be at least 10 characters'
    return null
  }

  const handleRegister = async () => {
    setLocalError(null)
    const v = validateRegister()
    if (v) return setLocalError(v)
    setLoading(true)
    try {
      await onRegister(username, email, password)
    } catch (e) {
      setLocalError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async () => {
    setLocalError(null)
    if (!username || !password) return setLocalError('Username and password required')
    setLoading(true)
    try {
      await onLogin(username, password)
    } catch (e) {
      setLocalError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="tabs">
          <button className={`tab ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>Login</button>
          <button className={`tab ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>Register</button>
        </div>

        <div className="auth-form">
          <input placeholder="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          {tab === 'register' && (
            <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
          <input placeholder="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />

          <div className="auth-actions">
            {tab === 'login' ? (
              <button className="primary" onClick={handleLogin} disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</button>
            ) : (
              <button className="primary" onClick={handleRegister} disabled={loading}>{loading ? 'Creating...' : 'Create account'}</button>
            )}
          </div>

          {(localError || error) && <div className="auth-error">{localError || error}</div>}

          {/* Logout button moved to the signed-in view in App.tsx */}
        </div>
      </div>
    </div>
  )
}

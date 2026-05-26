import './App.css'
import { useEffect, useRef, useState } from 'react';
import { streamHandleEmail, register, login, logoutAll, getValidAccessToken } from './api';
import InputForm from './components/inputForm/InputForm';
import OutputDisplay from './components/outputDisplay/OutputDisplay';
import AuthPanel from './components/auth/AuthPanel';
import Toast from './components/ui/Toast';

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: 'streaming' | 'final' | 'error'
}

type TurnSummary = {
  id: string
  prompt: string
  status: 'streaming' | 'done' | 'error'
  updatedAt: number
}

type CompletedResponse = {
  intent?: string
  metadata?: {
    total_duration?: number
    usage?: {
      prompt_tokens?: number
      completion_tokens?: number
      total_tokens?: number
      interaction_price?: number
    }
  }
  [key: string]: unknown
}

function makeId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const MAX_SESSION_TITLE_LENGTH = 24

function formatSessionTitle(title: string | null | undefined, createdAt: string) {
  const fallback = `Conversation ${new Date(createdAt).toLocaleString()}`
  const rawTitle = (title || '').trim() || fallback
  if (rawTitle.length <= MAX_SESSION_TITLE_LENGTH) return rawTitle
  return `${rawTitle.slice(0, MAX_SESSION_TITLE_LENGTH - 1).trimEnd()}…`
}

function App() {
  const [streamingText, setStreamingText] = useState('');
  const [completedResponse, setCompletedResponse] = useState<CompletedResponse | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [turns, setTurns] = useState<TurnSummary[]>([])
  const [archives, setArchives] = useState<Record<string, ChatMessage[]>>({})
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(localStorage.getItem('session_id'))
  const [sessions, setSessions] = useState<Array<{id:string,title:string,created_at:string,last_updated:string}>>([])
  const transcriptEndRef = useRef<HTMLDivElement | null>(null)

  const [currentUser, setCurrentUser] = useState<string | null>(localStorage.getItem('username'));
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false)

  const clearConversation = () => {
    setStreamingText('')
    setCompletedResponse(null)
    setError('')
    setIsLoading(false)
    setMessages([])
    setTurns([])
    setCurrentSessionId(null)
    localStorage.removeItem('session_id')
  }

  const refreshSessions = async () => {
    try {
      const token = await getValidAccessToken()
      if (!token) return
      const resp = await fetch('http://localhost:8000/api/sessions', { headers: { Authorization: `Bearer ${token}` } })
      if (!resp.ok) return
      const body = await resp.json()
      setSessions(body.items || [])
    } catch {
      // ignore
    }
  }

  const fetchMessagesForSession = async (sessionId: string) => {
    const token = await getValidAccessToken()
    if (!token) return null
    const resp = await fetch(`http://localhost:8000/api/messages?session_id=${encodeURIComponent(sessionId)}&limit=500`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) return null
    const body = await resp.json()
    const items = body?.items || []
    return items.map((m: { role?: string; content?: string }, idx: number): ChatMessage => ({
      id: `${sessionId}-${idx}-${m.role}`,
      role: m.role === 'assistant' ? 'assistant' : 'user',
      content: m.content || '',
      status: 'final' as const,
    }))
  }

  const storeConversationMessages = (sessionId: string, nextMessages: ChatMessage[]) => {
    setMessages(nextMessages)
    setArchives((prev) => ({ ...prev, [sessionId]: nextMessages }))
  }

  const handleSubmit = async (emailText: string) => {
    const trimmed = emailText.trim()
    if (!trimmed) return

    // ensure we have a session
    let sid = currentSessionId
    let createdSession = false
    if (!sid) {
      try {
        const token = await getValidAccessToken()
        if (token) {
          const resp = await fetch('http://localhost:8000/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ title: trimmed.slice(0, 80) }) })
          if (resp.ok) {
            const body = await resp.json()
            sid = body.session_id
            if (!sid) return
            createdSession = true
            setCurrentSessionId(sid)
            localStorage.setItem('session_id', sid)
          }
        }
      } catch {
        sid = makeId()
        setCurrentSessionId(sid)
      }
    }

    if (!sid) return

    const turnId = makeId()
    const assistantId = `${turnId}-assistant`
    let assistantText = ''

    const userMessage: ChatMessage = { id: `${turnId}-user`, role: 'user', content: trimmed }
    const assistantMessage: ChatMessage = { id: assistantId, role: 'assistant', content: 'Thinking...', status: 'streaming' }
    const baseConversation = archives[sid] || []
    const nextConversation = [...baseConversation, userMessage, assistantMessage]
    storeConversationMessages(sid, nextConversation)

    // persist user message to server (best-effort)
    ;(async () => {
      try {
        const token = await getValidAccessToken()
        if (!token) return
        await fetch('http://localhost:8000/api/messages', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ session_id: sid, role: 'user', content: trimmed, token_count: 0 }),
        })
      } catch {
        // ignore persistence errors
      }
    })()
    setTurns((prev) => [
      { id: turnId, prompt: trimmed.slice(0, 96), status: 'streaming' as const, updatedAt: Date.now() },
      ...prev,
    ].slice(0, 8))
    setStreamingText('');
    setCompletedResponse(null);
    setError('');
    setIsLoading(true);

    await streamHandleEmail(
      trimmed,
      (delta) => {
        assistantText += delta
        setStreamingText((prev) => prev + delta);
        setMessages((prev) => prev.map((message) => (
          message.id === assistantId
            ? { ...message, content: (message.status === 'streaming' && message.content === 'Thinking...') ? delta : message.content + delta }
            : message
        )))
        setArchives((prev) => {
          const copy = { ...prev }
          const a = copy[sid!]
          if (a) {
            const updated = a.map((message) => (
              message.id === assistantId
                ? { ...message, content: (message.status === 'streaming' && message.content === 'Thinking...') ? delta : message.content + delta }
                : message
            ))
            copy[sid!] = updated
          }
          return copy
        })
      },
      (response) => {
        setCompletedResponse(response as CompletedResponse);
        setMessages((prev) => prev.map((message) => (
          message.id === assistantId
            ? { ...message, content: assistantText || message.content, status: 'final' as const }
            : message
        )))
        setArchives((prev) => {
          const copy = { ...prev }
          const a = copy[sid!]
          if (a) {
            const updated = a.map((message): ChatMessage => (
              message.id === assistantId
                ? { ...message, content: assistantText || message.content, status: 'final' as const }
                : message
            ))
            copy[sid!] = updated
          }
          return copy
        })
        ;(async () => {
          try {
            const token = await getValidAccessToken()
            if (!token) return
            await fetch('http://localhost:8000/api/messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ session_id: sid, role: 'assistant', content: assistantText || '', token_count: 0 }),
            })
          } catch {
            // ignore persistence errors
          }
        })()
        setTurns((prev) => prev.map((turn) => (
          turn.id === turnId
            ? { ...turn, status: 'done', updatedAt: Date.now() }
            : turn
        )))
        setIsLoading(false);
      },
      (errorMsg) => {
        setTurns((prev) => prev.map((turn) => (
          turn.id === turnId
            ? { ...turn, status: 'error', updatedAt: Date.now() }
            : turn
        )))
        setIsLoading(false);
        void refreshSessions()
        // persist assistant final message
        ;(async () => {
          try {
            const token = await getValidAccessToken()
            if (!token) return
            await fetch('http://localhost:8000/api/messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ session_id: sid, role: 'assistant', content: assistantText || '', token_count: 0 }),
            })
          } catch {
            // ignore
          }
        })()
        // persist assistant error message
        ;(async () => {
          try {
            const token = await getValidAccessToken()
            if (!token) return
            await fetch('http://localhost:8000/api/messages', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify({ session_id: sid, role: 'assistant', content: errorMsg, token_count: 0 }),
            })
          } catch {
            // ignore
          }
        })()
        void refreshSessions()
      }
    );

    if (createdSession) {
      void refreshSessions()
    }
    await refreshSessions()
  };

  const loadTurn = async (turnId: string) => {
    try {
      const fromServer = await fetchMessagesForSession(turnId)
      if (fromServer && fromServer.length) {
        storeConversationMessages(turnId, fromServer)
        return
      }
    } catch {
      // ignore and fall back to local data
    }

    const archived = archives[turnId]
    if (archived && archived.length) {
      setMessages(archived)
      return
    }
    const userMsg = messages.find((m) => m.id.startsWith(`${turnId}-user`))
    const assistantMsg = messages.find((m) => m.id.startsWith(`${turnId}-assistant`))
    const arr: ChatMessage[] = []
    if (userMsg) arr.push(userMsg)
    if (assistantMsg) arr.push(assistantMsg)
    if (arr.length) setMessages(arr)
  }

  const handleRegister = async (username: string, email: string, password: string) => {
    setError('')
    try {
      const body = await register(username, email, password)
      if (body.access_token) {
        localStorage.setItem('access_token', body.access_token)
        localStorage.setItem('refresh_token', body.refresh_token)
        localStorage.setItem('username', body.user.username)
        clearConversation()
        setCurrentUser(body.user.username)
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
        clearConversation()
        setCurrentUser(body.user.username)
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
      clearConversation()
      setCurrentUser(null)
    } catch (e) {
      setError(String(e))
    }
  }

  useEffect(() => {
    const onLoggedOut = () => {
      // clear UI and local tokens when refresh failed or server forced logout
      clearConversation()
      setCurrentUser(null)
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('username')
      setToastMessage('Session expired or invalid. Please sign in again.')
    }
    window.addEventListener('auth:logged_out', onLoggedOut)
    return () => window.removeEventListener('auth:logged_out', onLoggedOut)
  }, [])

  useEffect(() => {
    try {
      const el = transcriptEndRef.current as unknown as HTMLElement | null
      if (el && typeof el.scrollIntoView === 'function') {
        el.scrollIntoView({ behavior: 'smooth', block: 'end' })
      }
    } catch {
      // scrollIntoView may not be implemented in the test DOM (jsdom); ignore safely
    }
  }, [messages, streamingText, isLoading])

  // fetch server-side profile to detect admin role (auth-based)
  useEffect(() => {
    let cancelled = false
    const loadMe = async () => {
      try {
        const token = await getValidAccessToken()
        if (!token) {
          setIsAdmin(false)
          return
        }
        const resp = await fetch('http://localhost:8000/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        if (!resp.ok) {
          setIsAdmin(false)
          return
        }
        const body = await resp.json()
        const roles = body?.roles || []
        if (!cancelled) setIsAdmin(Array.isArray(roles) && roles.includes('admin'))
      } catch {
        if (!cancelled) setIsAdmin(false)
      }
    }
    if (currentUser) loadMe()
    return () => { cancelled = true }
  }, [currentUser])

  // load sessions list for the user
  useEffect(() => {
    let cancelled = false
    const loadSessions = async () => {
      try {
        const token = await getValidAccessToken()
        if (!token) return
        const resp = await fetch('http://localhost:8000/api/sessions', { headers: { Authorization: `Bearer ${token}` } })
        if (!resp.ok) return
        const body = await resp.json()
        if (!cancelled) setSessions(body.items || [])
      } catch {
        // ignore
      }
    }
    if (currentUser) loadSessions()
    return () => { cancelled = true }
  }, [currentUser])

  const editSessionTitle = async (sessionId: string) => {
    const newTitle = window.prompt('Enter a new title for this conversation')
    if (!newTitle) return
    try {
      const token = await getValidAccessToken()
      if (!token) return
      const resp = await fetch(`http://localhost:8000/api/sessions/${sessionId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ title: newTitle }) })
      if (resp.ok) {
        await refreshSessions()
      }
    } catch {
      // ignore
    }
  }

  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  const confirmDeleteSession = (sessionId: string) => {
    setSessionToDelete(sessionId)
    setShowDeleteModal(true)
  }

  const performDeleteSession = async () => {
    if (!sessionToDelete) return
    try {
      const token = await getValidAccessToken()
      if (!token) return
      const resp = await fetch(`http://localhost:8000/api/sessions/${sessionToDelete}`, { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } })
      if (resp.ok) {
        if (currentSessionId === sessionToDelete) {
          setCurrentSessionId(null)
          localStorage.removeItem('session_id')
          setMessages([])
        }
        await refreshSessions()
      }
    } catch {
      // ignore
    } finally {
      setShowDeleteModal(false)
      setSessionToDelete(null)
    }
  }


  return (
    <div className="app-container">
      {!currentUser ? (
        <div className="auth-shell">
          <AuthPanel onRegister={handleRegister} onLogin={handleLogin} error={error} />
        </div>
      ) : (
        <div className="app-shell">
          <aside className="sidebar-panel">
            <div className="sidebar-top">
              <div>
                <p className="eyebrow">Support Agent</p>
                <div className="app-title-small">Agent Chat</div>
              </div>
              <button className="ghost-button" onClick={clearConversation}>New chat</button>
            </div>

            {/* compact signed-in footer moved to sidebar footer (see below) */}

            {/* session info removed per UX guidance */}

            <div className="history-block">
              <div className="block-heading">
                <h2>Conversation history</h2>
                <span>{turns.length} turns</span>
              </div>
              <div className="history-list">
                {sessions.length === 0 ? (
                  <div className="empty-history">
                    <p>No conversations yet.</p>
                  </div>
                ) : sessions.map((s) => (
                  <article key={s.id} role="button" tabIndex={0} onClick={() => { setCurrentSessionId(s.id); localStorage.setItem('session_id', s.id); loadTurn(s.id) }} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setCurrentSessionId(s.id); localStorage.setItem('session_id', s.id); loadTurn(s.id) } }} className={`history-item ${currentSessionId === s.id ? 'history-active' : ''}`}>
                    <div className="history-topline">
                      <strong title={s.title || `Conversation ${new Date(s.created_at).toLocaleString()}`}>{formatSessionTitle(s.title, s.created_at)}</strong>
                      <div style={{display:'flex', gap:8, alignItems:'center'}}>
                        <button
                          className="icon-button"
                          type="button"
                          title="Rename conversation"
                          aria-label="Rename conversation"
                          onClick={(e) => { e.stopPropagation(); editSessionTitle(s.id) }}
                        >
                          ✏️
                        </button>
                        <button
                          className="icon-button danger"
                          type="button"
                          title="Delete conversation"
                          aria-label="Delete conversation"
                          onClick={(e) => { e.stopPropagation(); confirmDeleteSession(s.id) }}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                    <div className="history-time">{new Date(s.created_at).toLocaleDateString()}</div>
                  </article>
                ))}
              </div>
            </div>

            <div className="sidebar-footer">
              <div className="signed-in-compact">
                <strong>{currentUser}</strong>
                <button className="ghost-button danger" onClick={handleLogoutAll}>Log out</button>
              </div>
            </div>
          </aside>

          <main className="chat-shell">
            <section className="chat-surface">
              <header className="chat-surface-header">
                <div>
                  <p className="eyebrow">Conversation</p>
                </div>
              </header>

              <div className="message-stream" aria-live="polite">
                {messages.length === 0 ? null : messages.map((message) => (
                  <div key={message.id} className={`message-row ${message.role}`}>
                    <div className="message-avatar">{message.role === 'user' ? 'You' : 'AI'}</div>
                    <div className={`message-bubble ${message.status ?? ''}`}>
                      <div className="message-role">{message.role === 'user' ? 'User' : 'Agent'}</div>
                      <div className="message-content">{message.content}</div>
                    </div>
                  </div>
                ))}
                <div ref={transcriptEndRef} />
              </div>

              {isAdmin && (
                <details className="debug-drawer">
                  <summary>Debug & memory</summary>
                  <OutputDisplay
                    streamingText={streamingText}
                    completedResponse={completedResponse}
                    error={error}
                    isStreaming={isLoading}
                  />
                </details>
              )}
            </section>

            <div className="composer-shell">
              <InputForm onSubmit={handleSubmit} isLoading={isLoading} />
            </div>
          </main>
        </div>
      )}
      {toastMessage && <Toast message={toastMessage} onClose={() => setToastMessage(null)} />}

      {showDeleteModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3>Delete conversation?</h3>
            <p>Are you sure you want to permanently delete this conversation and its messages? This cannot be undone.</p>
            <div className="actions">
              <button className="secondary" onClick={() => { setShowDeleteModal(false); setSessionToDelete(null) }}>Cancel</button>
              <button className="danger" onClick={performDeleteSession}>Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App


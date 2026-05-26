/* @vitest-environment jsdom */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'

const globalScope = globalThis as typeof globalThis & { localStorage?: Storage }

if (
  typeof globalScope.localStorage === 'undefined' ||
  typeof globalScope.localStorage.getItem !== 'function' ||
  typeof globalScope.localStorage.setItem !== 'function' ||
  typeof globalScope.localStorage.removeItem !== 'function' ||
  typeof globalScope.localStorage.clear !== 'function'
) {
  const store = new Map<string, string>()
  globalScope.localStorage = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  } as Storage
}

type SessionRecord = {
  id: string
  title: string
  created_at: string
  last_updated: string
}

type MessageRecord = {
  role: 'user' | 'assistant'
  content: string
  token_count: number
}

function buildJwt(payload: Record<string, unknown>) {
  const b64 = btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `a.${b64}.c`
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  })
}

function sseResponse(events: Array<Record<string, unknown>>) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      controller.close()
    },
  })
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

describe('conversation persistence', () => {
  let sessions: SessionRecord[]
  let messagesBySession: Map<string, MessageRecord[]>
  let sessionCounter: number

  beforeEach(() => {
    localStorage.clear()
    sessions = []
    messagesBySession = new Map()
    sessionCounter = 0

    const future = Math.floor(Date.now() / 1000) + 3600
    localStorage.setItem('access_token', buildJwt({ exp: future }))
    localStorage.setItem('refresh_token', 'refresh-token')
    localStorage.setItem('username', 'tester')

    vi.stubGlobal('fetch', async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? new URL(input) : new URL(input.url)
      const method = (init?.method || 'GET').toUpperCase()

      if (url.pathname === '/api/auth/me') {
        return jsonResponse({ user: { id: 1, username: 'tester', email: 'tester@example.com' }, roles: [] })
      }

      if (url.pathname === '/api/sessions' && method === 'POST') {
        const body = init?.body ? JSON.parse(String(init.body)) as { title?: string } : {}
        sessionCounter += 1
        const now = new Date(Date.now() + sessionCounter * 1000).toISOString()
        const record: SessionRecord = {
          id: `session-${sessionCounter}`,
          title: body.title || '',
          created_at: now,
          last_updated: now,
        }
        sessions = [record, ...sessions]
        messagesBySession.set(record.id, [])
        return jsonResponse({ status: 'ok', session_id: record.id })
      }

      if (url.pathname === '/api/sessions' && method === 'GET') {
        return jsonResponse({ items: sessions })
      }

      if (url.pathname === '/api/messages' && method === 'POST') {
        const body = init?.body ? JSON.parse(String(init.body)) as { session_id?: string; role: 'user' | 'assistant'; content: string; token_count?: number } : null
        if (body?.session_id) {
          const existing = messagesBySession.get(body.session_id) || []
          existing.push({ role: body.role, content: body.content, token_count: body.token_count || 0 })
          messagesBySession.set(body.session_id, existing)

          sessions = sessions.map((session) => (
            session.id === body.session_id
              ? { ...session, last_updated: new Date(Date.now() + existing.length * 1000).toISOString() }
              : session
          ))
        }
        return jsonResponse({ status: 'ok', message_id: 'mock-message-id' })
      }

      if (url.pathname === '/api/messages' && method === 'GET') {
        const sessionId = url.searchParams.get('session_id')
        const items = sessionId ? (messagesBySession.get(sessionId) || []) : []
        return jsonResponse({ items })
      }

      if (url.pathname === '/api/handle' && method === 'POST') {
        const body = init?.body ? JSON.parse(String(init.body)) as { email_text?: string } : {}
        const responseText = body.email_text?.includes('First') ? 'First AI response' : 'Second AI response'
        return sseResponse([
          { type: 'delta', data: { text: responseText.slice(0, 10) } },
          { type: 'delta', data: { text: responseText.slice(10) } },
          {
            type: 'completed',
            data: {
              intent: 'simple',
              response_text: responseText,
              metadata: {
                total_duration: 0.1,
                usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2, interaction_price: 0 },
              },
            },
          },
        ])
      }

      return jsonResponse({})
    })
  })

  it('keeps assistant messages attached to each saved conversation when reopening old chats', async () => {
    render(<App />)

    expect(await screen.findByText('tester')).toBeInTheDocument()

    const composer = screen.getByPlaceholderText('Enter your support email text here...')
    const sendButton = screen.getByRole('button', { name: 'Send Request' })

    fireEvent.change(composer, { target: { value: 'First billing issue' } })
    fireEvent.click(sendButton)

    expect(await screen.findByText('First billing issue', { selector: '.history-topline strong' })).toBeInTheDocument()
    expect(await screen.findByText('First AI response', { selector: '.message-content' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    fireEvent.change(composer, { target: { value: 'Second shipping issue' } })
    fireEvent.click(sendButton)

    expect(await screen.findByText('Second shipping issue', { selector: '.history-topline strong' })).toBeInTheDocument()
    expect(await screen.findByText('Second AI response', { selector: '.message-content' })).toBeInTheDocument()

    fireEvent.click(screen.getByText('First billing issue', { selector: '.history-topline strong' }))

    await waitFor(() => expect(screen.getByText('First AI response', { selector: '.message-content' })).toBeInTheDocument())
    expect(screen.getByText('First billing issue', { selector: '.history-topline strong' })).toBeInTheDocument()
    expect(screen.queryByText('Second AI response', { selector: '.message-content' })).not.toBeInTheDocument()
  })
})
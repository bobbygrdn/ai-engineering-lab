/* @vitest-environment jsdom */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { streamHandleEmail } from '../api'

// Ensure a minimal localStorage implementation exists for this test file.
if (
  typeof (globalThis as any).localStorage === 'undefined' ||
  typeof (globalThis as any).localStorage.getItem !== 'function' ||
  typeof (globalThis as any).localStorage.setItem !== 'function' ||
  typeof (globalThis as any).localStorage.removeItem !== 'function' ||
  typeof (globalThis as any).localStorage.clear !== 'function'
) {
  const store = new Map<string, string>()
  ;(globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  }
}

function buildJwt(payload: Record<string, unknown>) {
  const p = btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `a.${p}.c`
}

describe('streamHandleEmail auth handling', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns auth-required error when no token is available', async () => {
    const onDelta = vi.fn()
    const onComplete = vi.fn()
    const onError = vi.fn()

    await streamHandleEmail('hello', onDelta, onComplete, onError)

    expect(onError).toHaveBeenCalledWith('Authentication required. Please sign in again.')
    expect(onDelta).not.toHaveBeenCalled()
    expect(onComplete).not.toHaveBeenCalled()
  })

  it('dispatches logout event and error message on 401', async () => {
    const token = buildJwt({ exp: Math.floor(Date.now() / 1000) + 3600 })
    localStorage.setItem('access_token', token)
    localStorage.setItem('refresh_token', 'r')
    localStorage.setItem('username', 'tester')

    const onDelta = vi.fn()
    const onComplete = vi.fn()
    const onError = vi.fn()
    const logoutSpy = vi.fn()
    window.addEventListener('auth:logged_out', logoutSpy)

    global.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ detail: 'unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    }) as unknown as typeof fetch

    await streamHandleEmail('hello', onDelta, onComplete, onError)

    expect(onError).toHaveBeenCalledWith('Session expired or invalid. Please sign in again.')
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('username')).toBeNull()
    expect(logoutSpy).toHaveBeenCalled()

    window.removeEventListener('auth:logged_out', logoutSpy)
  })
})

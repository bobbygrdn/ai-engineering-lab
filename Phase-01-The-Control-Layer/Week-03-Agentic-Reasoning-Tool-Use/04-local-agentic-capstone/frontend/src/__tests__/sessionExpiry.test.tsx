/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react'
import App from '../App'
import { getValidAccessToken } from '../api'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'

// register jest-dom matchers with Vitest's expect
expect.extend(matchers as any)

// Ensure a minimal `localStorage` implementation exists in this test
if (typeof (globalThis as any).localStorage === 'undefined' || typeof (globalThis as any).localStorage.getItem !== 'function') {
  const store = new Map<string, string>()
  ;(globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  }
}

describe('session expiry flow', () => {
  beforeEach(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    // ensure App's event listeners are mounted fresh
  })

  it('shows a toast and clears tokens when refresh fails', async () => {
    render(<App />)

    // create an expired access token (simple fake JWT with expired exp)
    const payload = { exp: Math.floor(Date.now() / 1000) - 60 }
    const b64 = btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
    const fakeAccess = `a.${b64}.c`
    localStorage.setItem('access_token', fakeAccess)
    localStorage.setItem('refresh_token', 'bad-refresh')
    localStorage.setItem('username', 'tester')

    // stub fetch to make refresh endpoint return 401
    vi.stubGlobal('fetch', async (input: RequestInfo, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (url.includes('/api/auth/refresh')) {
        return new Response(JSON.stringify({ detail: 'invalid' }), { status: 401, headers: { 'Content-Type': 'application/json' } })
      }
      // default fallback
      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    // call the token refresh helper which should fail and dispatch the event
    await getValidAccessToken()

    // the App should react to the auth:logged_out event and show Toast
    const toast = await screen.findByRole('status')
    expect(toast).toHaveTextContent('Session expired or invalid')

    // tokens should be removed
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('username')).toBeNull()
  })
})

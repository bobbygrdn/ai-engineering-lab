/* @vitest-environment jsdom */

import { render, screen } from '@testing-library/react'
import App from '../App'
import { describe, it, expect, beforeEach } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers as any)

if (typeof (globalThis as any).localStorage === 'undefined' || typeof (globalThis as any).localStorage.getItem !== 'function') {
  const store = new Map<string, string>()
  ;(globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  }
}

function buildJwt(payload: Record<string, unknown>) {
  const b64 = btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `a.${b64}.c`
}

describe('session health badge', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('shows healthy badge for a signed-in user with a valid token', async () => {
    const future = Math.floor(Date.now() / 1000) + 3600
    localStorage.setItem('access_token', buildJwt({ exp: future }))
    localStorage.setItem('refresh_token', 'r')
    localStorage.setItem('username', 'tester')

    render(<App />)

    expect(await screen.findByText(/Signed in as/i)).toBeInTheDocument()
    const badge = await screen.findByLabelText('session-health')
    expect(badge).toHaveTextContent('Session: Healthy')
  })
})

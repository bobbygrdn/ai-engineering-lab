import { getValidAccessToken } from '../api'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// Minimal localStorage polyfill
const makeLocalStorage = () => {
  const store = new Map<string, string>()
  return {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => store.set(k, String(v)),
    removeItem: (k: string) => store.delete(k),
    clear: () => store.clear(),
  }
}

describe('getValidAccessToken refresh failure', () => {
  beforeEach(() => {
    // reset globals - create simple getItem stub; we won't call setItem in this test
    const store = new Map<string, string>()
    store.set('access_token', 'expired.token.here')
    store.set('refresh_token', 'bad-refresh')
    store.set('username', 'tester')
    ;(globalThis as any).localStorage = {
      getItem: (k: string) => (store.has(k) ? store.get(k) : null),
      setItem: (k: string, v: string) => (store.set(k, String(v)), undefined),
      removeItem: (k: string) => (store.delete(k), undefined),
      clear: () => (store.clear(), undefined),
    }
    ;(globalThis as any).window = globalThis
  })

  it('clears tokens and dispatches auth:logged_out when refresh fails', async () => {
    // initial values provided by the localStorage stub in beforeEach

    // spy on dispatchEvent using a wrapper to avoid TDZ issues
    ;(globalThis as any)._dispatchSpy = vi.fn()
    ;(globalThis as any).dispatchEvent = (...args: any[]) => (globalThis as any)._dispatchSpy(...args)

    // mock fetch to return 401 for refresh
    global.fetch = vi.fn(async (input: RequestInfo) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      if (url.includes('/api/auth/refresh')) {
        return new Response(JSON.stringify({ detail: 'invalid' }), { status: 401, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }) as unknown as typeof fetch

    const token = await getValidAccessToken()
    expect(token).toBeNull()
    expect((globalThis as any).localStorage.getItem('access_token')).toBeNull()
    expect((globalThis as any).localStorage.getItem('refresh_token')).toBeNull()
    expect((globalThis as any).localStorage.getItem('username')).toBeNull()
    expect((globalThis as any)._dispatchSpy).toHaveBeenCalled()
  })
})

/* @vitest-environment jsdom */

import { describe, it, expect, vi } from 'vitest'
import { subscribeToAuthLogout } from '../components/ui/SessionNotifier'

describe('SessionNotifier helper', () => {
  it('calls the callback when auth:logged_out is dispatched and respects unsubscribe', () => {
    const cb = vi.fn()
    const unsubscribe = subscribeToAuthLogout(cb)

    // trigger the event
    window.dispatchEvent(new Event('auth:logged_out'))
    expect(cb).toHaveBeenCalledWith('Session expired or invalid. Please sign in again.')
    expect(cb).toHaveBeenCalledTimes(1)

    // unsubscribe and ensure no further calls
    unsubscribe()
    window.dispatchEvent(new Event('auth:logged_out'))
    expect(cb).toHaveBeenCalledTimes(1)
  })
})

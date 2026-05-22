import { useEffect, useState } from 'react'
import Toast from './Toast'

// Exported helper so we can unit-test the event subscription without mounting React
export function subscribeToAuthLogout(cb: (message: string) => void) {
  const handler = () => cb('Session expired or invalid. Please sign in again.')
  window.addEventListener('auth:logged_out', handler)
  return () => window.removeEventListener('auth:logged_out', handler)
}

export default function SessionNotifier() {
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const unsubscribe = subscribeToAuthLogout((msg) => setMessage(msg))
    return () => unsubscribe()
  }, [])

  if (!message) return null
  return <Toast message={message} onClose={() => setMessage(null)} />
}

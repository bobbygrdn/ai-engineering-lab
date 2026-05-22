import { useEffect } from 'react'

type Props = {
  message: string
  duration?: number
  onClose?: () => void
}

export default function Toast({ message, duration = 4000, onClose }: Props) {
  useEffect(() => {
    const t = setTimeout(() => onClose && onClose(), duration)
    return () => clearTimeout(t)
  }, [duration, onClose])

  return (
    <div className="toast" role="status" aria-live="polite">
      {message}
      <button className="toast-close" onClick={() => onClose && onClose()} aria-label="Close">×</button>
    </div>
  )
}

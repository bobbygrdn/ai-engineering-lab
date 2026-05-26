export async function backendHeartbeat() {
    const response = await fetch('http://localhost:8000/api/heartbeat')
    return await response.json()
}

function parseJwt(token: string) {
    try {
        const parts = token.split('.')
        if (parts.length !== 3) return null
        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
        const decoded = atob(payload.padEnd(payload.length + (4 - (payload.length % 4)) % 4, '='))
        return JSON.parse(decoded)
    } catch {
        return null
    }
}

export async function refreshToken(refresh_token: string) {
    const resp = await fetch('http://localhost:8000/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token }),
    })
    return resp.json()
}

export async function getValidAccessToken() {
    const access = localStorage.getItem('access_token')
    const refresh = localStorage.getItem('refresh_token')
    const leeway = 30 // seconds

    if (access) {
        const payload = parseJwt(access)
        if (payload && payload.exp && (Date.now() / 1000) < (payload.exp - leeway)) {
            return access
        }
    }

    if (!refresh) return null

    try {
        const body = await refreshToken(refresh)
        if (body && body.access_token) {
            localStorage.setItem('access_token', body.access_token)
            if (body.refresh_token) localStorage.setItem('refresh_token', body.refresh_token)
            if (body.user && body.user.username) localStorage.setItem('username', body.user.username)
            return body.access_token
        }
    } catch (e) {
        console.error('Refresh failed', e)
    }

    // If refresh failed, clear tokens
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('username')
    try {
        window.dispatchEvent(new CustomEvent('auth:logged_out'))
    } catch {
        // ignore in non-browser contexts
    }
    return null
}

async function fetchWithAuth(input: RequestInfo, init?: RequestInit) {
    init = init || {}
    const baseHeaders: Record<string, string> = {}
    if (init.headers) {
        // copy existing headers (may be Headers, array or object)
        try {
            const h = new Headers(init.headers as HeadersInit)
            h.forEach((v, k) => (baseHeaders[k] = v))
        } catch {
            // fallback: ignore
        }
    }

    // attach current access token if present (no proactive refresh)
    const current = localStorage.getItem('access_token')
    if (current) baseHeaders['Authorization'] = `Bearer ${current}`

    const firstResp = await fetch(input, { ...init, headers: baseHeaders })
    if (firstResp.status !== 401) return firstResp

    // Try to refresh and retry once
    const newToken = await getValidAccessToken()
    if (!newToken) return firstResp

    const retryHeaders = { ...(baseHeaders || {}) }
    retryHeaders['Authorization'] = `Bearer ${newToken}`
    return await fetch(input, { ...init, headers: retryHeaders })
}

export async function register(username: string, email: string, password: string) {
    const resp = await fetch('http://localhost:8000/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
    })
    return resp.json()
}

export async function login(username: string, password: string) {
    const resp = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    })
    return resp.json()
}

export async function logout(refresh_token: string) {
    const resp = await fetch('http://localhost:8000/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token }),
    })
    return resp.json()
}

export async function logoutAll() {
    const resp = await fetchWithAuth('http://localhost:8000/api/auth/logout-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
    return resp.json()
}

export async function classifyEmail(emailText: string) {
    const response = await fetch('http://localhost:8000/api/classify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email_text: emailText }),
    });

    const data = await response.json();
    return data;
}

export async function streamHandleEmail(
    emailText: string,
    onDelta: (text: string) => void,
    onComplete: (response: unknown) => void,
    onError: (error: string) => void,
    onStatus?: (status: unknown) => void
) {
    try {
        const token = await getValidAccessToken()
        if (!token) {
            onError('Authentication required. Please sign in again.')
            return
        }

        const response = await fetch('http://localhost:8000/api/handle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({ email_text: emailText }),
        });

        if (response.status === 401) {
            try {
                localStorage.removeItem('access_token')
                localStorage.removeItem('refresh_token')
                localStorage.removeItem('username')
                window.dispatchEvent(new CustomEvent('auth:logged_out'))
            } catch {
                // ignore in non-browser contexts
            }
            onError('Session expired or invalid. Please sign in again.')
            return
        }

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error('Response body is not readable');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Split by SSE event boundaries (\n\n)
            const events = buffer.split('\n\n');
            buffer = events.pop() || ''; // Keep incomplete event in buffer

            for (const event of events) {
                if (!event.trim()) continue;

                // Parse SSE format: "data: {json}"
                const lines = event.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const json = JSON.parse(line.slice(6));
                            
                            if (json.type === 'delta') {
                                onDelta(json.data.text);
                            } else if (json.type === 'done') {
                                // Text streaming complete, response still coming
                            } else if (json.type === 'policy_review') {
                                if (onStatus) onStatus(json.data)
                            } else if (json.type === 'completed') {
                                if (onStatus && json.data?.policy_review) onStatus(json.data.policy_review)
                                onComplete(json.data);
                            } else if (json.type === 'error') {
                                onError(json.data.message);
                            }
                        } catch (e) {
                            console.error('Failed to parse event:', line, e);
                        }
                    }
                }
            }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
            const lines = buffer.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const json = JSON.parse(line.slice(6));
                        if (json.type === 'completed') {
                            if (onStatus && json.data?.policy_review) onStatus(json.data.policy_review)
                            onComplete(json.data);
                        } else if (json.type === 'delta') {
                            onDelta(json.data.text);
                        } else if (json.type === 'policy_review') {
                            if (onStatus) onStatus(json.data)
                        } else if (json.type === 'error') {
                            onError(json.data.message);
                        }
                    } catch (e) {
                        console.error('Failed to parse final event:', line, e);
                    }
                }
            }
        }
    } catch (error) {
        onError(error instanceof Error ? error.message : String(error));
    }
}

export type SessionHealthStatus = 'healthy' | 'expiring' | 'expired' | 'missing'

export function getSessionHealthSnapshot(
    expiringWindowSeconds: number = 120
): { status: SessionHealthStatus; label: string; secondsRemaining: number | null } {
    const access = localStorage.getItem('access_token')
    if (!access) {
        return { status: 'missing', label: 'Missing', secondsRemaining: null }
    }

    const payload = parseJwt(access)
    if (!payload || !payload.exp) {
        return { status: 'expired', label: 'Expired', secondsRemaining: null }
    }

    const now = Math.floor(Date.now() / 1000)
    const remaining = Number(payload.exp) - now
    if (remaining <= 0) {
        return { status: 'expired', label: 'Expired', secondsRemaining: 0 }
    }
    if (remaining <= expiringWindowSeconds) {
        return { status: 'expiring', label: 'Expiring', secondsRemaining: remaining }
    }
    return { status: 'healthy', label: 'Healthy', secondsRemaining: remaining }
}
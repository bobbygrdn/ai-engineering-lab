export async function backendHeartbeat() {
    const response = await fetch('http://localhost:8000/api/heartbeat')
    return await response.json()
}
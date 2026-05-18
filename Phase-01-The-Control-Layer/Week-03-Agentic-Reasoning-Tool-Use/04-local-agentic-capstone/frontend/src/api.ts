export async function backendHeartbeat() {
    const response = await fetch('http://localhost:8000/api/heartbeat')
    return await response.json()
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
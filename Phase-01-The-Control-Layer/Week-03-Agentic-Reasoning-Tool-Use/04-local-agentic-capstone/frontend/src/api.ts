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

export async function streamHandleEmail(
    emailText: string,
    onDelta: (text: string) => void,
    onComplete: (response: any) => void,
    onError: (error: string) => void
) {
    try {
        const response = await fetch('http://localhost:8000/api/handle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email_text: emailText }),
        });

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
                            } else if (json.type === 'completed') {
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
                            onComplete(json.data);
                        } else if (json.type === 'delta') {
                            onDelta(json.data.text);
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
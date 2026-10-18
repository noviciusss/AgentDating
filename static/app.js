/* Agent Dating — client-side helpers */

/**
 * Connect to SSE stream for run progress.
 * Falls back to polling if SSE drops.
 */
function connectProgress(runId, onUpdate, onDone) {
    const source = new EventSource(`/api/runs/${runId}/events`);
    let pollTimer = null;

    source.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (onUpdate) onUpdate(data);
            if (data.stage === 'done') {
                source.close();
                if (onDone) onDone(data);
            }
        } catch (e) {
            console.error('SSE parse error:', e);
        }
    };

    source.onerror = () => {
        source.close();
        console.warn('SSE dropped, falling back to polling');
        if (!pollTimer) {
            pollTimer = setInterval(async () => {
                try {
                    const res = await fetch(`/api/runs/${runId}`);
                    const data = await res.json();
                    if (onUpdate) onUpdate({ stage: data.current_stage, message: `Status: ${data.status}` });
                    if (data.status === 'completed' || data.status === 'failed') {
                        clearInterval(pollTimer);
                        if (onDone) onDone(data);
                    }
                } catch (_) {}
            }, 2000);
        }
    };

    return source;
}

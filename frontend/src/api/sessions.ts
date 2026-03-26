import { request, setSessionId, sessionId } from "./client";

let ensureSessionInFlight: Promise<string> | null = null;

export async function ensureSession(): Promise<string> {
    if (ensureSessionInFlight) {
        return ensureSessionInFlight;
    }

    ensureSessionInFlight = (async () => {
    const existing = sessionId();
    if (existing) {
        try {
            await request<{ id: string }>("GET", `/sessions/${encodeURIComponent(existing)}`);
            return existing;
        } catch {
            setSessionId(null);
        }
    }
    const payload = await request<{ sessionId: string }>("POST", "/sessions", {
        channel: "web",
        initialContext: {},
    });
    setSessionId(payload.sessionId);
    return payload.sessionId;
    })();

    try {
        return await ensureSessionInFlight;
    } finally {
        ensureSessionInFlight = null;
    }
}

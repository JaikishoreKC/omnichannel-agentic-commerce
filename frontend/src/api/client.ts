import type { ChatResponsePayload } from "./types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/v1";
const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
const SESSION_KEY = "commerce_session_id";
const AUTH_KEY = "commerce_access_token";
const REFRESH_KEY = "commerce_refresh_token";

type Method = "GET" | "POST" | "PUT" | "DELETE";

type ValidationErrorItem = {
    loc?: Array<string | number>;
    msg?: string;
};

type WsEnvelope = {
    type: string;
    sessionId?: string;
    streamId?: string;
    payload?: Record<string, unknown>;
};

export function token(): string | null {
    return localStorage.getItem(AUTH_KEY);
}

export function setToken(value: string | null): void {
    if (value) {
        localStorage.setItem(AUTH_KEY, value);
        return;
    }
    localStorage.removeItem(AUTH_KEY);
}

export function sessionId(): string | null {
    return localStorage.getItem(SESSION_KEY);
}

export { sessionId as currentSessionId };

export function setSessionId(value: string | null): void {
    if (value) {
        localStorage.setItem(SESSION_KEY, value);
        return;
    }
    localStorage.removeItem(SESSION_KEY);
}

export function setRefreshToken(value: string | null): void {
    if (value) {
        localStorage.setItem(REFRESH_KEY, value);
        return;
    }
    localStorage.removeItem(REFRESH_KEY);
}

export function getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY);
}

/** Clear all auth state and dispatch a global event so AuthContext can redirect */
function clearAuthAndNotify(): void {
    setToken(null);
    setRefreshToken(null);
    localStorage.removeItem("commerce_user");
    window.dispatchEvent(new CustomEvent("auth:expired"));
}

/** Attempt a silent token refresh using the stored refresh token. */
let _isRefreshing = false;
let _refreshQueue: Array<() => void> = [];

async function tryRefreshToken(): Promise<boolean> {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    if (_isRefreshing) {
        // Another refresh is in-flight; queue up and wait for it
        return new Promise((resolve) => _refreshQueue.push(() => resolve(!!token())));
    }

    _isRefreshing = true;
    try {
        const response = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refreshToken }),
        });
        if (!response.ok) return false;
        const data = await response.json();
        const newAccess: string = data.accessToken;
        const newRefresh: string = data.refreshToken;
        if (!newAccess) return false;
        setToken(newAccess);
        if (newRefresh) setRefreshToken(newRefresh);
        return true;
    } catch {
        return false;
    } finally {
        _isRefreshing = false;
        const queue = _refreshQueue;
        _refreshQueue = [];
        queue.forEach((fn) => fn());
    }
}

export async function request<T>(
    method: Method,
    path: string,
    body?: unknown,
    extraHeaders: Record<string, string> = {},
): Promise<T> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...extraHeaders,
    };

    const savedToken = token();
    if (savedToken) {
        headers.Authorization = `Bearer ${savedToken}`;
    }

    const savedSession = sessionId();
    if (savedSession) {
        headers["X-Session-Id"] = savedSession;
    }

    const response = await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });

    // --- Global 401 handler: try silent refresh, then force logout ---
    if (response.status === 401 && path !== "/auth/refresh") {
        const refreshed = await tryRefreshToken();
        if (refreshed) {
            // Retry the original request with the new token
            return request<T>(method, path, body, extraHeaders);
        }
        clearAuthAndNotify();
        throw new Error("Session expired. Please log in again.");
    }

    if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
            const payload = await response.json();
            const rawDetail = payload.error?.message ?? payload.detail;
            if (rawDetail) {
                if (Array.isArray(rawDetail)) {
                    detail = rawDetail
                        .map((err) => {
                            const item = err as ValidationErrorItem;
                            const loc = Array.isArray(item.loc) ? item.loc.join(".") : "field";
                            const message = typeof item.msg === "string" ? item.msg : "invalid";
                            return `${loc}: ${message}`;
                        })
                        .join(", ");
                } else {
                    detail = String(rawDetail);
                }
            }
        } catch {
            // Keep fallback error detail.
        }
        throw new Error(detail);
    }

    if (response.status === 204) {
        return {} as T;
    }
    return (await response.json()) as T;
}

export function connectChat(params: {
    sessionId: string;
    onMessage: (payload: ChatResponsePayload, streamId?: string) => void;
    onSession: (sessionId: string) => void;
    onError: (message: string) => void;
    onTyping?: (payload: { actor?: string; isTyping: boolean }) => void;
    onStreamStart?: (payload: { streamId: string; agent?: string }) => void;
    onStreamDelta?: (payload: { streamId: string; delta: string }) => void;
    onStreamEnd?: (payload: { streamId: string }) => void;
    onOpen?: () => void;
    onClose?: () => void;
}): WebSocket {
    const socket = new WebSocket(`${WS_BASE}?sessionId=${encodeURIComponent(params.sessionId)}`);
    
    socket.onopen = () => {
        params.onOpen?.();
    };
    
    socket.onmessage = (event) => {
        try {
            const parsed = JSON.parse(event.data as string) as WsEnvelope;
            if (parsed.type === "session" && parsed.payload?.sessionId) {
                const nextSessionId = String(parsed.payload.sessionId);
                setSessionId(nextSessionId);
                params.onSession(nextSessionId);
                return;
            }
            if (parsed.type === "ping") {
                socket.send(JSON.stringify({ type: "pong", payload: parsed.payload }));
                return;
            }
            if (parsed.type === "typing" && parsed.payload && typeof parsed.payload.isTyping === "boolean") {
                params.onTyping?.({
                    actor: typeof parsed.payload.actor === "string" ? parsed.payload.actor : undefined,
                    isTyping: parsed.payload.isTyping,
                });
                return;
            }
            if (parsed.type === "response" && parsed.payload) {
                params.onMessage(parsed.payload as unknown as ChatResponsePayload, parsed.streamId);
                return;
            }
            if (parsed.type === "stream_start" && parsed.payload?.streamId) {
                params.onStreamStart?.({
                    streamId: String(parsed.payload.streamId),
                    agent: typeof parsed.payload.agent === "string" ? parsed.payload.agent : undefined,
                });
                return;
            }
            if (parsed.type === "stream_delta" && parsed.payload?.streamId) {
                params.onStreamDelta?.({
                    streamId: String(parsed.payload.streamId),
                    delta: String(parsed.payload.delta ?? ""),
                });
                return;
            }
            if (parsed.type === "stream_end" && parsed.payload?.streamId) {
                params.onStreamEnd?.({
                    streamId: String(parsed.payload.streamId),
                });
                return;
            }
            if (parsed.type === "error") {
                params.onError(typeof parsed.payload?.message === "string" ? parsed.payload.message : "Unknown websocket error");
            }
        } catch {
            params.onError("Failed to parse websocket message.");
        }
    };
    socket.onerror = () => {
        params.onError("WebSocket connection error.");
    };
    socket.onclose = () => {
        params.onClose?.();
    };
    return socket;
}

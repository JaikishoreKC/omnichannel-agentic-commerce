import { beforeEach, describe, expect, it, vi } from "vitest";
import { connectChat } from "./client";

class MockWebSocket {
    static instances: MockWebSocket[] = [];
    onopen: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: (() => void) | null = null;
    onclose: (() => void) | null = null;

    sent: string[] = [];

    constructor(public url: string) {
        MockWebSocket.instances.push(this);
    }

    send(payload: string): void {
        this.sent.push(payload);
    }

    close(): void {
        this.onclose?.();
    }

    emitMessage(payload: unknown): void {
        this.onmessage?.({ data: JSON.stringify(payload) });
    }
}

describe("client websocket contract", () => {
    beforeEach(() => {
        MockWebSocket.instances = [];
        vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
        const storage = new Map<string, string>();
        const localStorageMock = {
            getItem: (key: string) => storage.get(key) ?? null,
            setItem: (key: string, value: string) => storage.set(key, value),
            removeItem: (key: string) => storage.delete(key),
        };
        vi.stubGlobal("localStorage", localStorageMock);
        vi.stubGlobal("window", {
            dispatchEvent: vi.fn(),
        });
    });

    it("routes status events to onStatus callback", () => {
        const onStatus = vi.fn();

        connectChat({
            sessionId: "s1",
            onMessage: vi.fn(),
            onSession: vi.fn(),
            onError: vi.fn(),
            onStatus,
            onTyping: vi.fn(),
            onStreamStart: vi.fn(),
            onStreamDelta: vi.fn(),
            onStreamEnd: vi.fn(),
        });

        const ws = MockWebSocket.instances[0];
        ws.emitMessage({ type: "status", payload: { code: "provider_busy", message: "busy" } });

        expect(onStatus).toHaveBeenCalledWith({ code: "provider_busy", message: "busy" });
    });

    it("routes stream envelopes and final response with streamId", () => {
        const onStreamStart = vi.fn();
        const onStreamDelta = vi.fn();
        const onStreamEnd = vi.fn();
        const onMessage = vi.fn();

        connectChat({
            sessionId: "s2",
            onMessage,
            onSession: vi.fn(),
            onError: vi.fn(),
            onStatus: vi.fn(),
            onTyping: vi.fn(),
            onStreamStart,
            onStreamDelta,
            onStreamEnd,
        });

        const ws = MockWebSocket.instances[0];
        ws.emitMessage({ type: "stream_start", payload: { streamId: "stream_1", agent: "cart" } });
        ws.emitMessage({ type: "stream_delta", payload: { streamId: "stream_1", delta: "hello" } });
        ws.emitMessage({ type: "stream_end", payload: { streamId: "stream_1" } });
        ws.emitMessage({ type: "response", streamId: "stream_1", payload: { message: "", agent: "cart", data: {}, suggestedActions: [], metadata: {} } });

        expect(onStreamStart).toHaveBeenCalledWith({ streamId: "stream_1", agent: "cart" });
        expect(onStreamDelta).toHaveBeenCalledWith({ streamId: "stream_1", delta: "hello" });
        expect(onStreamEnd).toHaveBeenCalledWith({ streamId: "stream_1" });
        expect(onMessage).toHaveBeenCalledWith(
            { message: "", agent: "cart", data: {}, suggestedActions: [], metadata: {} },
            "stream_1",
        );
    });
});

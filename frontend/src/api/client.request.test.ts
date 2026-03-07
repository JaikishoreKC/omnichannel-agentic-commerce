import { beforeEach, describe, expect, it, vi } from "vitest";
import { request, setSessionId, setToken } from "./client";

describe("client request auth headers", () => {
    beforeEach(() => {
        const storage = new Map<string, string>();
        vi.stubGlobal("localStorage", {
            getItem: (key: string) => storage.get(key) ?? null,
            setItem: (key: string, value: string) => {
                storage.set(key, value);
            },
            removeItem: (key: string) => {
                storage.delete(key);
            },
        });
        vi.stubGlobal("window", {
            dispatchEvent: vi.fn(),
        });
        setToken(null);
        setSessionId(null);
    });

    it("sends bearer and session headers when available", async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ ok: true }),
        });
        vi.stubGlobal("fetch", fetchMock);

        setToken("access_123");
        setSessionId("session_123");

        await request<{ ok: boolean }>("GET", "/admin/stats");

        expect(fetchMock).toHaveBeenCalledTimes(1);
        const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
        const headers = options.headers as Record<string, string>;
        expect(headers.Authorization).toBe("Bearer access_123");
        expect(headers["X-Session-Id"]).toBe("session_123");
    });
});

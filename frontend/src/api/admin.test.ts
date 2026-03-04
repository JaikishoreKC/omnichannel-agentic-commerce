import { beforeEach, describe, expect, it, vi } from "vitest";
import { getHealth } from "./admin";

describe("admin api contracts", () => {
    beforeEach(() => {
        vi.restoreAllMocks();
    });

    it("queries health endpoint outside /v1 and returns json", async () => {
        const payload = {
            status: "ok",
            services: {
                llm: {
                    enabled: true,
                    provider: "openrouter",
                    circuitBreakerState: "closed",
                },
            },
        };

        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => payload,
        });
        vi.stubGlobal("fetch", fetchMock);

        const result = await getHealth();

        expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/health");
        expect(result.services.llm.circuitBreakerState).toBe("closed");
    });

    it("throws when health endpoint returns non-2xx", async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: false });
        vi.stubGlobal("fetch", fetchMock);

        await expect(getHealth()).rejects.toThrow("Failed to fetch health");
    });
});

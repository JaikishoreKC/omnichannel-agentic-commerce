import { beforeEach, describe, expect, it, vi } from "vitest";
import {
    getAdminCategories,
    getAdminInventory,
    getAdminSupportTickets,
    getHealth,
    updateAdminSupportTicket,
    updateVoiceSettings,
} from "./admin";
import { request } from "./client";

vi.mock("./client", () => ({
    request: vi.fn(),
}));

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

        expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/health", { credentials: "include" });
        expect(result.services.llm.circuitBreakerState).toBe("closed");
    });

    it("throws when health endpoint returns non-2xx", async () => {
        const fetchMock = vi.fn().mockResolvedValue({ ok: false });
        vi.stubGlobal("fetch", fetchMock);

        await expect(getHealth()).rejects.toThrow("Failed to fetch health");
    });

    it("builds support ticket admin query string", async () => {
        vi.mocked(request).mockResolvedValue({ tickets: [] });

        await getAdminSupportTickets({ status: "open", userId: "u1", limit: 30 });

        expect(request).toHaveBeenCalledWith("GET", "/admin/support/tickets?status=open&userId=u1&limit=30");
    });

    it("uses patch endpoint for admin support ticket updates", async () => {
        vi.mocked(request).mockResolvedValue({ ticket: { id: "t1", status: "resolved" } });

        await updateAdminSupportTicket("t1", { status: "resolved", note: "done" });

        expect(request).toHaveBeenCalledWith("PATCH", "/admin/support/tickets/t1", {
            status: "resolved",
            note: "done",
        });
    });

    it("uses category status filter and inventory/voice endpoints", async () => {
        vi.mocked(request).mockResolvedValueOnce({ categories: [] });
        vi.mocked(request).mockResolvedValueOnce({ inventory: { variantId: "v1" } });
        vi.mocked(request).mockResolvedValueOnce({ settings: { killSwitch: true } });

        await getAdminCategories("active");
        await getAdminInventory("v1");
        await updateVoiceSettings({ killSwitch: true });

        expect(request).toHaveBeenNthCalledWith(1, "GET", "/admin/categories/records?status=active");
        expect(request).toHaveBeenNthCalledWith(2, "GET", "/admin/inventory/v1");
        expect(request).toHaveBeenNthCalledWith(3, "PUT", "/admin/voice/settings", { killSwitch: true });
    });
});

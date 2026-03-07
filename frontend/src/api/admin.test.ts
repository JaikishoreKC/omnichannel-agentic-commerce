import { beforeEach, describe, expect, it, vi } from "vitest";
import {
    createProduct,
    getAdminCategories,
    getAdminStats,
    getAdminInventory,
    getAdminSupportTickets,
    getHealth,
    updateProduct,
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

    it("maps canonical stats payload with compatibility fallbacks", async () => {
        vi.mocked(request).mockResolvedValueOnce({
            totalRevenue: 123.45,
            activeUsers: 22,
            pendingOrders: 5,
            totalProducts: 11,
        });

        const stats = await getAdminStats();

        expect(request).toHaveBeenCalledWith("GET", "/admin/stats");
        expect(stats.totalRevenue).toBe(123.45);
        expect(stats.activeUsers).toBe(22);
        expect(stats.pendingOrders).toBe(5);
        expect(stats.totalProducts).toBe(11);

        vi.mocked(request).mockResolvedValueOnce({
            revenueToday: 88,
            activeSessions: 7,
            pendingOrders: 0,
            totalProducts: 0,
        });

        const fallbackStats = await getAdminStats();
        expect(fallbackStats.totalRevenue).toBe(88);
        expect(fallbackStats.activeUsers).toBe(7);
    });

    it("unwraps product create response envelope", async () => {
        vi.mocked(request).mockResolvedValueOnce({
            product: {
                id: "prod_123",
                name: "Test Product",
                category: "apparel",
                price: 49.99,
                variants: [],
            },
        });

        const product = await createProduct({
            name: "Test Product",
            description: "desc",
            category: "apparel",
            price: 49.99,
        });

        expect(request).toHaveBeenCalledWith("POST", "/admin/products", {
            name: "Test Product",
            description: "desc",
            category: "apparel",
            price: 49.99,
        });
        expect(product.id).toBe("prod_123");
    });

        it("unwraps product update response envelope", async () => {
            vi.mocked(request).mockResolvedValueOnce({
                product: {
                    id: "prod_123",
                    name: "Updated Product",
                    category: "apparel",
                    price: 59.99,
                    status: "draft",
                    variants: [],
                },
            });

            const product = await updateProduct("prod_123", {
                name: "Updated Product",
                price: 59.99,
                status: "draft",
            });

            expect(request).toHaveBeenCalledWith("PUT", "/admin/products/prod_123", {
                name: "Updated Product",
                price: 59.99,
                status: "draft",
            });
            expect(product.name).toBe("Updated Product");
            expect(product.status).toBe("draft");
        });
});

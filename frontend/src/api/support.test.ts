import { beforeEach, describe, expect, it, vi } from "vitest";
import { createSupportTicket, listSupportTickets, updateSupportTicket } from "./support";
import { request } from "./client";

vi.mock("./client", () => ({
    request: vi.fn(),
}));

describe("support api contracts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("builds support ticket list query params", async () => {
        vi.mocked(request).mockResolvedValue({ tickets: [] });

        await listSupportTickets({ status: "in_progress", limit: 25 });

        expect(request).toHaveBeenCalledWith("GET", "/support/tickets?status=in_progress&limit=25");
    });

    it("posts support ticket create payload", async () => {
        vi.mocked(request).mockResolvedValue({ ticket: { id: "t1" } });

        await createSupportTicket({ issue: "Need help", category: "general", priority: "normal", channel: "web" });

        expect(request).toHaveBeenCalledWith("POST", "/support/tickets", {
            issue: "Need help",
            category: "general",
            priority: "normal",
            channel: "web",
        });
    });

    it("uses PATCH endpoint for support ticket updates", async () => {
        vi.mocked(request).mockResolvedValue({ ticket: { id: "t1", status: "resolved" } });

        await updateSupportTicket("t1", { status: "resolved", note: "Resolved in account tab" });

        expect(request).toHaveBeenCalledWith("PATCH", "/support/tickets/t1", {
            status: "resolved",
            note: "Resolved in account tab",
        });
    });
});

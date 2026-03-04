import { beforeEach, describe, expect, it, vi } from "vitest";
import { deleteMemoryPreference, fetchMemoryHistory, updateMemoryPreferences } from "./memory";
import { request } from "./client";

vi.mock("./client", () => ({
    request: vi.fn(),
}));

describe("memory api contracts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("sends direct updates object for preferences", async () => {
        vi.mocked(request).mockResolvedValue(undefined);

        await updateMemoryPreferences({ categories: ["Shoes"] });

        expect(request).toHaveBeenCalledWith("PUT", "/memory/preferences", { categories: ["Shoes"] });
    });

    it("uses history envelope shape", async () => {
        const historyEnvelope = {
            history: [
                {
                    id: "evt_1",
                    userId: "u1",
                    eventType: "preference_update",
                    key: "categories",
                    value: ["Shoes"],
                    oldValue: [],
                    source: "chat",
                    timestamp: "2026-03-05T00:00:00Z",
                },
            ],
        };
        vi.mocked(request).mockResolvedValue(historyEnvelope);

        const result = await fetchMemoryHistory(10);

        expect(request).toHaveBeenCalledWith("GET", "/memory/history?limit=10");
        expect(result.history).toHaveLength(1);
    });

    it("encodes key and optional value in delete endpoint", async () => {
        vi.mocked(request).mockResolvedValue(undefined);

        await deleteMemoryPreference("brandPreferences", "New Balance");

        expect(request).toHaveBeenCalledWith(
            "DELETE",
            "/memory/preferences/brandPreferences?value=New%20Balance",
        );
    });
});

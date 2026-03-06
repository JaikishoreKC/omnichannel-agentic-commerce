import { describe, expect, it } from "vitest";
import type { ChatResponsePayload } from "../api/types";
import type { InteractionHistoryMessage } from "../types";
import { applyFinalAssistantPayload, mapHistoryRowsToMessages, toSuggestedActionUtterance } from "./ChatContext";

describe("ChatContext helper invariants", () => {
    it("maps history into separate user/assistant turns with correct roles", () => {
        const rows: InteractionHistoryMessage[] = [
            {
                id: "evt_1",
                sessionId: "s1",
                userId: null,
                message: "hello",
                intent: "general_question",
                agent: "general",
                response: {
                    message: "hi there",
                    agent: "general",
                },
                timestamp: "2026-03-06T00:00:00Z",
            },
        ];

        const mapped = mapHistoryRowsToMessages(rows);
        expect(mapped).toHaveLength(2);
        expect(mapped[0].role).toBe("user");
        expect(mapped[0].content).toBe("hello");
        expect(mapped[1].role).toBe("assistant");
        expect(mapped[1].content).toBe("hi there");
    });

    it("does not append an empty assistant message for non-stream final payload", () => {
        const payload: ChatResponsePayload = {
            message: "",
            agent: "general",
            data: {},
            suggestedActions: [],
            metadata: {},
        };

        const prev = [
            {
                id: "m1",
                role: "user" as const,
                content: "hi",
                timestamp: "2026-03-06T00:00:00Z",
            },
        ];

        const next = applyFinalAssistantPayload(prev, payload);
        expect(next).toEqual(prev);
    });

    it("merges streamed final metadata into existing stream bubble by streamId", () => {
        const payload: ChatResponsePayload = {
            message: "",
            agent: "cart",
            data: { cart: { itemCount: 1 } },
            suggestedActions: [{ label: "View cart", action: "view_cart" }],
            metadata: {},
        };

        const prev = [
            {
                id: "stream_1",
                role: "assistant" as const,
                content: "Added to cart.",
                timestamp: "2026-03-06T00:00:00Z",
                isStreaming: true,
            },
        ];

        const next = applyFinalAssistantPayload(prev, payload, "stream_1");
        expect(next).toHaveLength(1);
        expect(next[0].id).toBe("stream_1");
        expect(next[0].content).toBe("Added to cart.");
        expect(next[0].isStreaming).toBe(false);
        expect(next[0].agent).toBe("cart");
        expect(next[0].suggestedActions).toEqual([{ label: "View cart", action: "view_cart" }]);
    });

    it("maps canonical suggested actions to deterministic utterances", () => {
        expect(toSuggestedActionUtterance({ label: "Show cart", action: "view_cart" })).toBe("show cart");
        expect(toSuggestedActionUtterance({ label: "Checkout", action: "checkout" })).toBe("checkout");
        expect(toSuggestedActionUtterance({ label: "Continue shopping", action: "search:more" })).toBe("show me more products");
        expect(
            toSuggestedActionUtterance({
                label: "Add AeroThread",
                action: "add_to_cart:ai_prod_1:ai_var_1",
            })
        ).toBe("add product ai_prod_1 variant ai_var_1 to cart");
    });
});

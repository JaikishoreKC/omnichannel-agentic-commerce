import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { connectChat, fetchChatHistory } from "../api";
import type { ChatResponsePayload } from "../api/types";
import { useSession } from "./SessionContext";

export type Message = {
    id: string;
    role: "user" | "assistant";
    content: string;
    agent?: string;
    timestamp: string;
    isStreaming?: boolean;
    suggestedActions?: Array<{ label: string; action: string }>;
};

interface ChatContextType {
    messages: Message[];
    isTyping: boolean;
    isConnected: boolean;
    isConnecting: boolean;
    sendMessage: (text: string) => void;
    clearMessages: () => void;
}

type HistoryMessage = {
    id: string;
    role?: "user" | "assistant";
    userId?: string | null;
    message: string;
    timestamp: string;
    agent?: string;
};

const ChatContext = createContext<ChatContextType | undefined>(undefined);

function shouldRefreshCart(payload: ChatResponsePayload): boolean {
    const agent = String(payload.agent || "").toLowerCase();
    if (agent === "cart" || agent === "order") {
        return true;
    }
    if (agent !== "orchestrator") {
        return false;
    }
    const data = payload.data;
    if (!data || typeof data !== "object") {
        return false;
    }
    return "cart" in data || "order" in data;
}

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { sessionId, isLoading: isSessionLoading, refreshSession } = useSession();
    const [messages, setMessages] = useState<Message[]>([]);
    const [isTyping, setIsTyping] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const connectingRef = useRef(false);
    const recoveringHistoryRef = useRef(false);

    const loadHistory = useCallback(async (activeSessionId: string) => {
        try {
            const history = await fetchChatHistory({ sessionId: activeSessionId });
            const mapped: Message[] = history.messages.map((m: HistoryMessage) => ({
                id: m.id,
                role: m.role || (m.userId ? "user" : "assistant"),
                content: m.message,
                timestamp: m.timestamp,
                agent: m.agent,
            }));
            setMessages(mapped);
            recoveringHistoryRef.current = false;
        } catch (err) {
            const detail = err instanceof Error ? err.message : "";
            const isSessionMismatch = /session mismatch/i.test(detail) || /^403\b/.test(detail);
            if (isSessionMismatch && !recoveringHistoryRef.current) {
                recoveringHistoryRef.current = true;
                await refreshSession();
                return;
            }
            recoveringHistoryRef.current = false;
            setMessages([]);
        }
    }, [refreshSession]);

    useEffect(() => {
        if (!sessionId || isSessionLoading) {
            return;
        }

        void loadHistory(sessionId);

        let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
        let attempts = 0;

        const connect = () => {
            // Guard against duplicate in-flight connection attempts.
            if (connectingRef.current || socketRef.current?.readyState === WebSocket.OPEN) {
                return;
            }
            connectingRef.current = true;
            setIsConnecting(true);
            const socket = connectChat({
                sessionId,
                onOpen: () => {
                    connectingRef.current = false;
                    setIsConnected(true);
                    setIsConnecting(false);
                    attempts = 0;
                },
                onClose: () => {
                    connectingRef.current = false;
                    setIsConnected(false);
                    setIsConnecting(false);
                    // Reconnect with exponential backoff (max 30s)
                    const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
                    reconnectTimer = setTimeout(() => {
                        attempts++;
                        connect();
                    }, delay);
                },
                onError: () => {
                    connectingRef.current = false;
                    setIsConnecting(false);
                },
                onSession: () => undefined,
                onTyping: ({ isTyping }) => setIsTyping(isTyping),
                onMessage: (payload, streamId) => {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: streamId || Date.now().toString(),
                            role: "assistant",
                            content: payload.message,
                            agent: payload.agent,
                            timestamp: new Date().toISOString(),
                            suggestedActions: payload.suggestedActions,
                        },
                    ]);
                    if (shouldRefreshCart(payload)) {
                        window.dispatchEvent(new CustomEvent("cart:refresh"));
                    }
                },
                onStreamStart: ({ streamId, agent }) => {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: streamId,
                            role: "assistant",
                            content: "",
                            agent,
                            timestamp: new Date().toISOString(),
                            isStreaming: true,
                        },
                    ]);
                },
                onStreamDelta: ({ streamId, delta }) => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === streamId ? { ...m, content: (m.content || "") + delta } : m
                        )
                    );
                },
                onStreamEnd: ({ streamId }) => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === streamId ? { ...m, isStreaming: false } : m
                        )
                    );
                },
            });
            socketRef.current = socket;
        };

        connect();

        return () => {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
            }
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [isSessionLoading, loadHistory, sessionId]);

    const sendMessage = (text: string) => {
        // Only send when socket is actually open.
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ 
                type: "message", 
                payload: { 
                    content: text,
                    stream: true
                } 
            }));
            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now().toString(),
                    role: "user",
                    content: text,
                    timestamp: new Date().toISOString(),
                },
            ]);
        }
    };

    const clearMessages = () => setMessages([]);

    return (
        <ChatContext.Provider
            value={{ messages, isTyping, isConnected, isConnecting, sendMessage, clearMessages }}
        >
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (context === undefined) {
        throw new Error("useChat must be used within a ChatProvider");
    }
    return context;
};

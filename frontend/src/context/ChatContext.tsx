import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { connectChat, fetchChatHistory } from "../api";
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

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { sessionId, isLoading: isSessionLoading } = useSession();
    const [messages, setMessages] = useState<Message[]>([]);
    const [isTyping, setIsTyping] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);
    const socketRef = useRef<WebSocket | null>(null);
    const connectingRef = useRef(false);  // Track connecting state to avoid race conditions

    const loadHistory = useCallback(async () => {
        if (!sessionId) return;
        try {
            const history = await fetchChatHistory({ sessionId });
            const mapped: Message[] = history.messages.map((m: any) => ({
                id: m.id,
                role: m.role || (m.userId ? "user" : "assistant"),
                content: m.message,
                timestamp: m.timestamp,
                agent: m.agent,
            }));
            setMessages(mapped);
        } catch (err) {
            console.error("Failed to load chat history", err);
        }
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId || isSessionLoading) {
            return;
        }

        loadHistory();

        let reconnectTimer: any;
        let attempts = 0;

        const connect = () => {
            // Don't attempt if already connecting or connected - use ref to avoid race condition
            if (connectingRef.current || socketRef.current?.readyState === WebSocket.OPEN) {
                return;
            }
            console.log(`Attempting to connect chat (attempt ${attempts + 1})...`);
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
                onError: (err) => console.error("Chat WS error", err),
                onSession: (sid) => console.log("Session updated via WS", sid),
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
                    window.dispatchEvent(new CustomEvent("cart:refresh"));
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
            clearTimeout(reconnectTimer);
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [sessionId, loadHistory]);

    const sendMessage = (text: string) => {
        // Only send when socket is actually open - checking readyState for reliability
        if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
            socketRef.current.send(JSON.stringify({ 
                type: "message", 
                payload: { 
                    content: text,
                    stream: true  // Enable streaming for proper LLM responses
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

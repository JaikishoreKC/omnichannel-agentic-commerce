import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, X, Send, Minus, Maximize2, Sparkles } from "lucide-react";
import { toSuggestedActionUtterance, useChat } from "../../context/ChatContext";
import { Button } from "../ui/Button";
import { cn } from "../../utils/cn";

function formatConfidence(value: unknown): string | null {
    if (typeof value === "number" && Number.isFinite(value)) {
        return `${Math.round(value * 100)}%`;
    }
    if (typeof value === "string" && value.trim()) {
        const parsed = Number(value);
        if (Number.isFinite(parsed)) {
            return `${Math.round(parsed * 100)}%`;
        }
    }
    return null;
}

function readAssistantHint(metadata: Record<string, unknown> | undefined): { intent?: string; confidence?: string } {
    if (!metadata) {
        return {};
    }
    const intent = typeof metadata.intent === "string" && metadata.intent.trim() ? metadata.intent : undefined;
    const confidence = formatConfidence(metadata.confidence) ?? undefined;
    return { intent, confidence };
}

const ChatPanel: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [inputValue, setInputValue] = useState("");
    const { messages, sendMessage, isTyping, assistantStatus, isConnected, isConnecting } = useChat();
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isTyping]);

    const handleSend = () => {
        if (!inputValue.trim() || !isConnected) return;
        sendMessage(inputValue.trim());
        setInputValue("");
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
            <AnimatePresence>
                {!isOpen && (
                    <motion.div
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                    >
                        <Button
                            onClick={() => setIsOpen(true)}
                            size="icon"
                            className="w-14 h-14 rounded-2xl shadow-panel bg-brand hover:bg-brand-dark"
                            aria-label="Open chat assistant"
                            title="Open chat assistant"
                        >
                            <MessageSquare className="text-white" />
                        </Button>
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ y: 20, opacity: 0, scale: 0.95 }}
                        animate={{
                            y: 0,
                            opacity: 1,
                            scale: 1,
                            height: isMinimized ? 64 : 500
                        }}
                        exit={{ y: 20, opacity: 0, scale: 0.95 }}
                        className={cn(
                            "w-[380px] bg-white rounded-3xl shadow-panel overflow-hidden border border-line flex flex-col",
                            isMinimized && "w-[240px]"
                        )}
                    >
                        {/* Header */}
                        <div className="bg-brand p-4 flex items-center justify-between text-white shrink-0">
                            <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
                                    <Sparkles size={16} className="text-white" />
                                </div>
                                <div>
                                    <h4 className="font-medium text-sm">AI Assistant</h4>
                                    {isMinimized ? (
                                        <div className="flex items-center gap-1.5" data-testid="chat-ready">
                                            <div className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-emerald-400" : isConnecting ? "bg-yellow-400 animate-pulse" : "bg-red-400")} />
                                            <span className="text-[10px] opacity-80">{isConnected ? "connected" : isConnecting ? "connecting..." : "disconnected"}</span>
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-1.5" data-testid="chat-ready">
                                            <div className={cn("w-1.5 h-1.5 rounded-full", isConnected ? "bg-emerald-400" : isConnecting ? "bg-yellow-400 animate-pulse" : "bg-red-400")} />
                                            <span className="text-[10px] opacity-80">{isConnected ? "connected" : isConnecting ? "connecting..." : "disconnected"}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-1">
                                <button
                                    onClick={() => setIsMinimized(!isMinimized)}
                                    className="p-1 hover:bg-white/10 rounded-lg transition-colors"
                                    aria-label={isMinimized ? "Expand chat" : "Minimize chat"}
                                    title={isMinimized ? "Expand chat" : "Minimize chat"}
                                >
                                    {isMinimized ? <Maximize2 size={16} /> : <Minus size={16} />}
                                </button>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    className="p-1 hover:bg-white/10 rounded-lg transition-colors"
                                    aria-label="Close chat"
                                    title="Close chat"
                                >
                                    <X size={16} />
                                </button>
                            </div>
                        </div>

                        {/* Chat Body */}
                        {!isMinimized && (
                            <>
                                <div
                                    ref={scrollRef}
                                    className="flex-1 overflow-y-auto p-4 space-y-4 bg-surface-50 chat-scroll-thin"
                                    data-testid="chat-log"
                                >
                                    {messages.length === 0 && (
                                        <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                                            <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center text-brand">
                                                <MessageSquare size={24} />
                                            </div>
                                            <p className="text-sm text-slate-500">
                                                Hello! I'm your Agentic Commerce assistant. How can I help you today?
                                            </p>
                                        </div>
                                    )}
                                    {messages.map((msg) => {
                                        const hint = readAssistantHint(msg.metadata);
                                        return (
                                        <div
                                            key={msg.id}
                                            className={cn(
                                                "flex flex-col max-w-[85%]",
                                                msg.role === "user" ? "ml-auto items-end" : "items-start"
                                            )}
                                        >
                                            <div
                                                className={cn(
                                                    "py-2.5 px-4 rounded-2xl text-sm leading-relaxed",
                                                    msg.role === "user"
                                                        ? "bg-brand text-white rounded-tr-none shadow-premium"
                                                        : "bg-white text-ink rounded-tl-none border border-line/50 shadow-sm"
                                                )}
                                            >
                                                {msg.content}
                                            </div>
                                            <span className="text-[10px] text-slate-400 mt-1 px-1">
                                                {msg.agent ? `${msg.agent} • ` : ""}{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                            {msg.role === "assistant" && (hint.intent || hint.confidence) && (
                                                <div className="mt-1 flex gap-1 px-1">
                                                    {hint.intent && (
                                                        <span className="text-[10px] text-slate-500 bg-slate-100 rounded-full px-2 py-0.5">
                                                            intent: {hint.intent}
                                                        </span>
                                                    )}
                                                    {hint.confidence && (
                                                        <span className="text-[10px] text-slate-500 bg-slate-100 rounded-full px-2 py-0.5">
                                                            confidence: {hint.confidence}
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                            {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                                                <div className="flex flex-wrap gap-2 mt-2 px-1">
                                                    {msg.suggestedActions.map((action, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => sendMessage(toSuggestedActionUtterance(action))}
                                                            className="text-xs px-3 py-1.5 bg-brand/10 text-brand font-medium rounded-full hover:bg-brand hover:text-white transition-colors border border-brand/20 whitespace-nowrap"
                                                        >
                                                            {action.label}
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        );
                                    })}
                                    {isTyping && (
                                        <div className="flex items-center gap-1 px-2">
                                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce typing-dot-0" />
                                            <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce typing-dot-150" />
                                            <div className="w-1.5 h-1.5 bg-slate-300 rounded-full animate-bounce typing-dot-300" />
                                        </div>
                                    )}
                                    {!isTyping && assistantStatus && (
                                        <div className="px-2">
                                            <span className="text-[11px] text-slate-500">{assistantStatus}</span>
                                        </div>
                                    )}
                                </div>

                                {/* Footer */}
                                <div className="p-4 border-t border-line bg-white">
                                    <div className="relative flex items-center">
                                        <input
                                            value={inputValue}
                                            onChange={(e) => setInputValue(e.target.value)}
                                            onKeyDown={(e) => e.key === "Enter" && handleSend()}
                                            placeholder="Ask anything..."
                                            className="w-full bg-surface-100 border-none rounded-xl pl-4 pr-12 py-3 text-sm focus:ring-2 focus:ring-brand/10 transition-all outline-none"
                                            data-testid="chat-input"
                                        />
                                        <Button
                                            onClick={handleSend}
                                            disabled={!inputValue.trim() || !isConnected}
                                            size="icon"
                                            className="absolute right-1.5 w-8 h-8 rounded-lg"
                                            data-testid="chat-send-button"
                                        >
                                            <Send size={14} />
                                        </Button>
                                    </div>
                                </div>
                            </>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export { ChatPanel };

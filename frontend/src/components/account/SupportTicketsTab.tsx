import React, { useEffect, useMemo, useState } from "react";
import { LifeBuoy, MessageSquare, ArrowRight, Clock, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { createSupportTicket, listSupportTickets, updateSupportTicket, type SupportTicket } from "../../api/support";
import { useToast } from "../../context/ToastContext";

export const SupportTicketsTab: React.FC = () => {
    const [tickets, setTickets] = useState<SupportTicket[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [issueText, setIssueText] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [resolvingTicketId, setResolvingTicketId] = useState<string | null>(null);
    const [inlineError, setInlineError] = useState<string | null>(null);
    const [activeFilter, setActiveFilter] = useState<string>("all");
    const { addToast } = useToast();

    const loadTickets = async (status?: string) => {
        try {
            setIsLoading(true);
            setInlineError(null);
            const rows = await listSupportTickets({
                status: status && status !== "all" ? status : undefined,
                limit: 50,
            });
            setTickets(rows);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to load support tickets";
            setInlineError(message);
            addToast(message, "error");
            setTickets([]);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadTickets(activeFilter);
    }, [activeFilter]);

    const grouped = useMemo(() => {
        return tickets.map((ticket) => ({
            ...ticket,
            latestMessage: ticket.messages?.[ticket.messages.length - 1]?.message || ticket.issue,
        }));
    }, [tickets]);

    const handleCreateTicket = async () => {
        if (!issueText.trim()) {
            addToast("Please describe your issue", "warning");
            return;
        }
        setIsSubmitting(true);
        try {
            setInlineError(null);
            await createSupportTicket({ issue: issueText.trim(), category: "general", priority: "normal", channel: "web" });
            addToast("Support ticket created", "success");
            setIssueText("");
            await loadTickets(activeFilter);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to create support ticket";
            setInlineError(message);
            addToast(message, "error");
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCloseTicket = async (ticketId: string) => {
        const confirmed = window.confirm("Mark this support ticket as resolved?");
        if (!confirmed) {
            return;
        }
        const previousTickets = [...tickets];
        setResolvingTicketId(ticketId);
        setInlineError(null);
        setTickets((prev) => prev.map((ticket) => ticket.id === ticketId ? { ...ticket, status: "resolved" } : ticket));
        try {
            await updateSupportTicket(ticketId, {
                status: "resolved",
                note: "Closed by customer from account support tab.",
            });
            addToast("Ticket marked as resolved", "success");
            await loadTickets(activeFilter);
        } catch (err) {
            setTickets(previousTickets);
            const message = err instanceof Error ? err.message : "Failed to update ticket";
            setInlineError(message);
            addToast(message, "error");
        } finally {
            setResolvingTicketId(null);
        }
    };

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600">
                        <LifeBuoy size={20} />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold">Support Conversations</h3>
                        <p className="text-xs text-slate-500">History of your AI agent interactions</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    {[
                        { id: "all", label: "All" },
                        { id: "open", label: "Open" },
                        { id: "in_progress", label: "In Progress" },
                        { id: "resolved", label: "Resolved" },
                    ].map((filter) => (
                        <Button
                            key={filter.id}
                            variant={activeFilter === filter.id ? "primary" : "outline"}
                            className="rounded-xl h-9 px-3 text-xs"
                            onClick={() => setActiveFilter(filter.id)}
                        >
                            {filter.label}
                        </Button>
                    ))}
                </div>
            </div>

            <div className="premium-card p-4 flex flex-col sm:flex-row gap-3">
                <Input
                    value={issueText}
                    onChange={(e) => setIssueText(e.target.value)}
                    placeholder="Describe your issue..."
                    className="flex-1"
                />
                <Button
                    className="rounded-xl gap-2 h-10 px-4 bg-ink hover:bg-slate-800"
                    onClick={handleCreateTicket}
                    disabled={isSubmitting}
                >
                    <MessageSquare size={16} /> New Request
                </Button>
            </div>

            <div className="space-y-4">
                {inlineError && (
                    <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                        {inlineError}
                    </div>
                )}
                {isLoading ? (
                    <div className="p-6 text-sm text-slate-500">Loading support tickets...</div>
                ) : grouped.length === 0 ? (
                    <div className="p-6 text-sm text-slate-500">No tickets found for this filter.</div>
                ) : grouped.map((t) => (
                    <div key={t.id} className="premium-card hover:border-brand/30 transition-all group">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-black text-slate-400">#{t.id}</span>
                                    <h4 className="font-bold text-slate-900">{t.issue}</h4>
                                </div>
                                <p className="text-xs text-slate-500 line-clamp-1">{t.latestMessage}</p>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="text-right">
                                    <div className="flex items-center gap-1.5 justify-end mb-1">
                                        <CheckCircle2 size={14} className="text-emerald-500" />
                                        <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">{t.status}</span>
                                    </div>
                                    <div className="text-[10px] text-slate-400 flex items-center gap-1 justify-end">
                                        <Clock size={10} /> {new Date(t.updatedAt).toLocaleDateString()}
                                    </div>
                                </div>
                                {t.status !== "resolved" && t.status !== "closed" ? (
                                    <button
                                        className="p-2 bg-surface-100 rounded-lg group-hover:bg-brand group-hover:text-white transition-all"
                                        aria-label={`Resolve support ticket ${t.id}`}
                                        title="Resolve ticket"
                                        disabled={resolvingTicketId === t.id}
                                        onClick={() => handleCloseTicket(t.id)}
                                    >
                                        <ArrowRight size={16} />
                                    </button>
                                ) : null}
                            </div>
                        </div>
                    </div>
                ))}

                <div className="p-8 border-2 border-dashed border-line rounded-[40px] bg-slate-50 text-center space-y-4">
                    <div className="w-12 h-12 rounded-2xl bg-white border border-line flex items-center justify-center mx-auto text-slate-400">
                        <LifeBuoy size={24} />
                    </div>
                    <div className="space-y-1">
                        <h4 className="font-bold text-slate-900">Need more help?</h4>
                        <p className="text-sm text-slate-500 max-w-xs mx-auto">
                            Our AI Agent is available 24/7 to solve your problems, track orders, or help with returns.
                        </p>
                    </div>
                    {/* In a real app, this would trigger opening the ChatPanel */}
                    <Button variant="outline" className="rounded-xl" onClick={() => window.dispatchEvent(new CustomEvent('chat:toggle'))}>
                        Chat with Agent
                    </Button>
                </div>
            </div>
        </div>
    );
};

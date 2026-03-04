import React from "react";
import { LifeBuoy, MessageSquare, ArrowRight, Clock, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/Button";

export const SupportTicketsTab: React.FC = () => {
    // Mocking some past support-oriented interactions
    const tickets = [
        {
            id: "SUP-8291",
            subject: "Delivery Delay Inquiry",
            status: "Resolved",
            date: "2024-03-01",
            lastMessage: "Your order is now out for delivery."
        },
        {
            id: "SUP-9012",
            subject: "Size Exchange help",
            status: "Closed",
            date: "2024-02-15",
            lastMessage: "I've started the return process for you."
        }
    ];

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
                <Button className="rounded-xl gap-2 h-10 px-4 bg-ink hover:bg-slate-800">
                    <MessageSquare size={16} /> New Request
                </Button>
            </div>

            <div className="space-y-4">
                {tickets.map((t) => (
                    <div key={t.id} className="premium-card hover:border-brand/30 transition-all group">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="space-y-1">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-black text-slate-400">#{t.id}</span>
                                    <h4 className="font-bold text-slate-900">{t.subject}</h4>
                                </div>
                                <p className="text-xs text-slate-500 line-clamp-1">{t.lastMessage}</p>
                            </div>
                            <div className="flex items-center gap-6">
                                <div className="text-right">
                                    <div className="flex items-center gap-1.5 justify-end mb-1">
                                        <CheckCircle2 size={14} className="text-emerald-500" />
                                        <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">{t.status}</span>
                                    </div>
                                    <div className="text-[10px] text-slate-400 flex items-center gap-1 justify-end">
                                        <Clock size={10} /> {t.date}
                                    </div>
                                </div>
                                <button className="p-2 bg-surface-100 rounded-lg group-hover:bg-brand group-hover:text-white transition-all">
                                    <ArrowRight size={16} />
                                </button>
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
                    <Button variant="outline" className="rounded-xl" onClick={() => (window as any).dispatchEvent(new CustomEvent('chat:toggle'))}>
                        Chat with Agent
                    </Button>
                </div>
            </div>
        </div>
    );
};

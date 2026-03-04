import React, { useEffect, useState } from "react";
import { BrainCircuit, Loader2, Sparkles, Trash2, Info } from "lucide-react";
import { Button } from "../ui/Button";
import { useToast } from "../../context/ToastContext";
import { request } from "../../api/client";

interface MemoryItem {
    id: string;
    key: string;
    value: any;
    created_at: string;
}

export const AiMemoryTab: React.FC = () => {
    const [memories, setMemories] = useState<MemoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const { addToast } = useToast();

    const fetchMemories = async () => {
        try {
            setIsLoading(true);
            const data = await request<MemoryItem[]>("GET", "/memory");
            setMemories(data);
        } catch (err) {
            console.error("Failed to fetch memories", err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchMemories();
    }, []);

    const handleDelete = async (key: string) => {
        try {
            await request("DELETE", `/memory/${key}`);
            addToast("Memory cleared", "success");
            fetchMemories();
        } catch (err) {
            addToast("Failed to clear memory", "error");
        }
    };

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600">
                        <BrainCircuit size={20} />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold">Personalization Memory</h3>
                        <p className="text-xs text-slate-500">How the AI understands your preferences</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className="hidden md:flex items-center gap-1.5 px-3 py-1 bg-amber-50 rounded-lg text-amber-700 text-[10px] font-bold uppercase tracking-wider border border-amber-100">
                        <Sparkles size={12} /> Adaptive Learning Active
                    </div>
                </div>
            </div>

            <div className="premium-card bg-indigo-50/30 border-indigo-100 flex items-start gap-4 p-6">
                <div className="p-2 bg-indigo-100 rounded-lg text-indigo-600 shrink-0">
                    <Info size={18} />
                </div>
                <div className="space-y-1">
                    <h4 className="text-sm font-bold text-indigo-900">What is AI Memory?</h4>
                    <p className="text-xs text-indigo-700 leading-relaxed">
                        To provide a truly personalized commerce experience, our agents remember your style preferences, preferred sizes, and shopping patterns. This data is private, stored securely, and used only to improve your recommendations.
                    </p>
                </div>
            </div>

            {isLoading ? (
                <div className="py-24 flex flex-col items-center justify-center space-y-4">
                    <Loader2 className="animate-spin text-indigo-500" size={32} />
                    <p className="text-slate-400 text-sm font-medium">Synthesizing personalization data...</p>
                </div>
            ) : memories.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {memories.map((m) => (
                        <div key={m.id} className="premium-card flex items-center justify-between group hover:border-indigo-200 transition-all duration-300">
                            <div>
                                <div className="text-[10px] uppercase tracking-widest font-black text-slate-400 mb-1">{m.key.replace(/_/g, ' ')}</div>
                                <div className="text-sm font-bold text-slate-800">
                                    {typeof m.value === 'object' ? JSON.stringify(m.value) : String(m.value)}
                                </div>
                            </div>
                            <button
                                onClick={() => handleDelete(m.key)}
                                className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center py-20 text-center space-y-4 border-2 border-dashed border-line rounded-[40px] bg-slate-50">
                    <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center text-slate-300">
                        <BrainCircuit size={32} />
                    </div>
                    <div className="space-y-1">
                        <h4 className="font-bold text-slate-900">Your memory is currently empty</h4>
                        <p className="text-sm text-slate-500 max-w-xs mx-auto">
                            As you interact with our agents and explore products, we'll start building a profile to better serve you.
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};

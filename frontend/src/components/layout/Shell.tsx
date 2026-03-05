import React from "react";
import { Navbar } from "./Navbar";
import { ChatPanel } from "../features/ChatPanel";
import { useLocation } from "react-router-dom";

const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const location = useLocation();
    const isAuthPage = ["/login", "/register", "/complete-profile"].includes(location.pathname);

    return (
        <div className="min-h-screen flex flex-col">
            {!isAuthPage && <Navbar />}

            <main className={isAuthPage ? "flex-1" : "flex-1 pt-24 pb-12"}>
                <div className={isAuthPage ? "" : "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"}>
                    {children}
                </div>
            </main>

            {!isAuthPage && <ChatPanel />}

            {!isAuthPage && (
                <footer className="py-12 border-t border-line bg-surface-50">
                    <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-6">
                        <div className="text-xl font-display font-bold text-brand">
                            AGENTIC<span className="text-ink">.</span>
                        </div>
                        <div className="text-sm text-slate-500">
                            © 2026 Omnichannel Agentic Commerce. All rights reserved.
                        </div>
                        <div className="flex gap-6">
                            <a href="#" className="text-sm text-slate-500 hover:text-brand transition-colors">Privacy</a>
                            <a href="#" className="text-sm text-slate-500 hover:text-brand transition-colors">Terms</a>
                        </div>
                    </div>
                </footer>
            )}
        </div>
    );
};

export { Shell };

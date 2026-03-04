import React, { createContext, useContext, useEffect, useState } from "react";
import { currentSessionId, ensureSession } from "../api";

interface SessionContextType {
    sessionId: string | null;
    isLoading: boolean;
    error: string | null;
    refreshSession: () => Promise<void>;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const storedSessionId = currentSessionId();
    const [sessionId, setSessionId] = useState<string | null>(storedSessionId);
    // If we already have a valid session, we're not loading
    const [isLoading, setIsLoading] = useState(!storedSessionId);
    const [error, setError] = useState<string | null>(null);

    const initSession = async () => {
        try {
            setIsLoading(true);
            const sid = await ensureSession();
            setSessionId(sid);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to initialize session");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        initSession();
    }, []);

    return (
        <SessionContext.Provider value={{ sessionId, isLoading, error, refreshSession: initSession }}>
            {children}
        </SessionContext.Provider>
    );
};

export const useSession = () => {
    const context = useContext(SessionContext);
    if (context === undefined) {
        throw new Error("useSession must be used within a SessionProvider");
    }
    return context;
};

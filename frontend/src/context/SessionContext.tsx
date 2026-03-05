import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { currentSessionId, ensureSession, SESSION_CHANGED_EVENT } from "../api";

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
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const initSession = useCallback(async () => {
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
    }, []);

    useEffect(() => {
        initSession();
    }, [initSession]);

    useEffect(() => {
        const syncSessionFromStorage = () => {
            setSessionId(currentSessionId());
        };

        const handleStorage = (event: StorageEvent) => {
            if (event.key === null || event.key === "commerce_session_id") {
                syncSessionFromStorage();
            }
        };

        const handleSessionChanged = () => {
            syncSessionFromStorage();
        };

        window.addEventListener("storage", handleStorage);
        window.addEventListener(SESSION_CHANGED_EVENT, handleSessionChanged);

        return () => {
            window.removeEventListener("storage", handleStorage);
            window.removeEventListener(SESSION_CHANGED_EVENT, handleSessionChanged);
        };
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

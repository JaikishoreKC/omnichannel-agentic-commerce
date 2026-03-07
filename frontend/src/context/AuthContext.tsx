import React, { createContext, useContext, useState, useEffect } from "react";
import {
    login as apiLogin,
    logout as apiLogout,
    register as apiRegister,
    updateProfile as apiUpdateProfile,
    setRefreshToken,
    setSessionId,
    setToken,
} from "../api";
import type { AuthUser } from "../types";

const PROFILE_COMPLETION_REQUIRED_KEY = "commerce_profile_completion_required";

const isCustomerProfileComplete = (user: AuthUser | null): boolean => {
    if (!user) return true;
    if (String(user.role).toLowerCase() !== "customer") return true;
    return Boolean(user.profileComplete);
};

const normalizeUser = (user: AuthUser): AuthUser => ({
    ...user,
    phone: user.phone ?? null,
    timezone: user.timezone ?? null,
    defaultShippingAddress: user.defaultShippingAddress ?? null,
    profileComplete: Boolean(user.profileComplete),
});

interface AuthContextType {
    user: AuthUser | null;
    isAuthenticated: boolean;
    isAdmin: boolean;
    profileCompletionRequired: boolean;
    login: (email: string, pass: string) => Promise<void>;
    loginAdmin: (email: string, pass: string, otp: string) => Promise<void>;
    register: (name: string, email: string, pass: string) => Promise<void>;
    updateProfile: (input: {
        name?: string;
        phone?: string;
        timezone?: string;
        defaultShippingAddress?: {
            name: string;
            line1: string;
            line2?: string;
            city: string;
            state: string;
            postalCode: string;
            country: string;
        };
    }) => Promise<AuthUser>;
    clearProfileCompletionRequirement: () => void;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<AuthUser | null>(() => {
        const saved = localStorage.getItem("commerce_user");
        if (!saved) return null;
        return normalizeUser(JSON.parse(saved) as AuthUser);
    });
    const [profileCompletionRequired, setProfileCompletionRequired] = useState<boolean>(() => {
        const saved = localStorage.getItem("commerce_user");
        if (saved) {
            const restoredUser = normalizeUser(JSON.parse(saved) as AuthUser);
            return !isCustomerProfileComplete(restoredUser);
        }
        return sessionStorage.getItem(PROFILE_COMPLETION_REQUIRED_KEY) === "1";
    });

    const isAuthenticated = !!user;
    const isAdmin = user?.role === "admin";

    // --- Global session-expiry handler ---
    // Listens for the `auth:expired` event dispatched by the API client's 401 interceptor.
    useEffect(() => {
        const handleExpired = () => {
            setUser(null);
            sessionStorage.removeItem(PROFILE_COMPLETION_REQUIRED_KEY);
            setProfileCompletionRequired(false);
            // Navigate to login with a "session expired" flag so we can show a notice
            window.location.href = "/login?expired=1";
        };
        window.addEventListener("auth:expired", handleExpired);
        return () => window.removeEventListener("auth:expired", handleExpired);
    }, []);

    const syncProfileCompletionRequirement = (nextUser: AuthUser) => {
        const required = !isCustomerProfileComplete(nextUser);
        if (required) {
            sessionStorage.setItem(PROFILE_COMPLETION_REQUIRED_KEY, "1");
        } else {
            sessionStorage.removeItem(PROFILE_COMPLETION_REQUIRED_KEY);
        }
        setProfileCompletionRequired(required);
    };

    const _applyAuth = (res: { user: AuthUser; accessToken?: string; refreshToken?: string; sessionId?: string }) => {
        const normalizedUser = normalizeUser(res.user);
        setUser(normalizedUser);
        if (res.accessToken) setToken(res.accessToken);
        if (res.refreshToken) setRefreshToken(res.refreshToken);
        if (res.sessionId) setSessionId(res.sessionId);
        localStorage.setItem("commerce_user", JSON.stringify(normalizedUser));
        syncProfileCompletionRequirement(normalizedUser);
    };

    const login = async (email: string, pass: string) => {
        const res = await apiLogin({ email, password: pass });
        if (res.user.role === "admin") {
            throw new Error("Admin accounts must sign in via the admin portal.");
        }
        _applyAuth(res);
    };

    const loginAdmin = async (email: string, pass: string, otp: string) => {
        const res = await apiLogin({ email, password: pass, otp });
        if (res.user.role !== "admin") {
            throw new Error("This portal is for admin accounts only.");
        }
        _applyAuth(res);
    };

    const register = async (name: string, email: string, pass: string) => {
        const res = await apiRegister({ name, email, password: pass });
        _applyAuth(res);
    };

    const updateProfile = async (input: {
        name?: string;
        phone?: string;
        timezone?: string;
        defaultShippingAddress?: {
            name: string;
            line1: string;
            line2?: string;
            city: string;
            state: string;
            postalCode: string;
            country: string;
        };
    }): Promise<AuthUser> => {
        const response = await apiUpdateProfile(input);
        const normalized = normalizeUser(response.user);
        setUser(normalized);
        localStorage.setItem("commerce_user", JSON.stringify(normalized));
        syncProfileCompletionRequirement(normalized);
        return normalized;
    };

    const clearProfileCompletionRequirement = () => {
        sessionStorage.removeItem(PROFILE_COMPLETION_REQUIRED_KEY);
        setProfileCompletionRequired(false);
    };

    const logout = async () => {
        try {
            await apiLogout();
        } catch {
            // local cleanup still proceeds if remote logout fails
        }
        setUser(null);
        setToken(null);
        setRefreshToken(null);
        setSessionId(null);
        sessionStorage.removeItem(PROFILE_COMPLETION_REQUIRED_KEY);
        setProfileCompletionRequired(false);
        localStorage.removeItem("commerce_user");
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated,
                isAdmin,
                profileCompletionRequired,
                login,
                loginAdmin,
                register,
                updateProfile,
                clearProfileCompletionRequirement,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};

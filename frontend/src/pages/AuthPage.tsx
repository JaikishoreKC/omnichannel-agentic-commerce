import React, { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Sparkles, ArrowRight } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

const AuthPage: React.FC = () => {
    const [mode, setMode] = useState<"login" | "register">("login");
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const { login, register } = useAuth();

    const [formData, setFormData] = useState({ name: "", email: "", password: "" });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(
        params.get("expired") === "1" ? "Your session has expired. Please sign in again." : null
    );

    const redirectUrl = params.get("redirect") || "/";

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        try {
            if (mode === "login") {
                await login(formData.email, formData.password);
            } else {
                await register(formData.name, formData.email, formData.password);
            }
            navigate(redirectUrl);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Authentication failed");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-[80vh] flex items-center justify-center p-4">
            <div className="w-full max-w-md space-y-8 animate-fade-in">
                <div className="text-center space-y-2">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-[24px] bg-brand/10 text-brand mb-4">
                        <Sparkles size={32} />
                    </div>
                    <h1 className="text-3xl font-bold">
                        {mode === "login" ? "Welcome Back" : "Create Account"}
                    </h1>
                    <p className="text-slate-500">
                        {mode === "login"
                            ? "Sign in to access your orders and settings"
                            : "Join our agency-driven commerce experience"}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="premium-card space-y-6">
                    {error && (
                        <div className="p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm font-medium text-center">
                            {error}
                        </div>
                    )}

                    {mode === "register" && (
                        <Input
                            label="Full Name"
                            placeholder="John Doe"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            required
                            data-testid="name-input"
                        />
                    )}

                    <Input
                        label="Email Address"
                        type="email"
                        placeholder="john@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        required
                        data-testid="email-input"
                    />

                    <Input
                        label="Password"
                        type="password"
                        placeholder="••••••••"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        required
                        data-testid="password-input"
                    />

                    {mode === "login" && (
                        <div className="flex justify-end -mt-2">
                            <button
                                type="button"
                                onClick={() => navigate("/forgot-password")}
                                className="text-xs font-semibold text-brand hover:text-brand-light transition-colors"
                            >
                                Forgot password?
                            </button>
                        </div>
                    )}

                    <Button
                        type="submit"
                        className="w-full h-12 rounded-2xl gap-2"
                        isLoading={isLoading}
                        data-testid="auth-submit-button"
                    >
                        {mode === "login" ? "Sign In" : "Get Started"} <ArrowRight size={18} />
                    </Button>

                    <div className="text-center text-sm text-slate-500">
                        {mode === "login" ? (
                            <>
                                Don't have an account?{" "}
                                <button type="button" onClick={() => setMode("register")} className="text-brand font-bold hover:underline">
                                    Sign Up
                                </button>
                            </>
                        ) : (
                            <>
                                Already have an account?{" "}
                                <button type="button" onClick={() => setMode("login")} className="text-brand font-bold hover:underline">
                                    Sign In
                                </button>
                            </>
                        )}
                    </div>
                </form>
            </div>
        </div>
    );
};

export { AuthPage };

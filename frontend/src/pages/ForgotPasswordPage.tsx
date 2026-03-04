import React, { useState } from "react";
import { Mail, ArrowRight, ShieldCheck, ChevronLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { request } from "../api/client";
import { useToast } from "../context/ToastContext";

export const ForgotPasswordPage: React.FC = () => {
    const navigate = useNavigate();
    const { addToast } = useToast();
    const [email, setEmail] = useState("");
    const [loading, setLoading] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!email) return;
        setLoading(true);
        try {
            await request("POST", "/auth/reset-password-request", { email });
            setSubmitted(true);
            addToast("If an account exists, a link was sent to your email", "success");
        } catch (err: any) {
            addToast(err.message || "Failed to process request", "error");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-[80vh] flex flex-col items-center justify-center p-4">
            <div className="w-full max-w-md space-y-8 animate-fade-in">
                <div className="text-center">
                    <div className="w-16 h-16 bg-brand/10 text-brand rounded-2xl flex items-center justify-center mx-auto mb-6 transform -rotate-6 shadow-sm border border-brand/20">
                        <ShieldCheck size={32} />
                    </div>
                    <h2 className="text-3xl font-bold tracking-tight">Reset Password</h2>
                    <p className="mt-2 text-sm text-slate-500">
                        Enter your email address and we'll send you a link to reset your password.
                    </p>
                </div>

                {submitted ? (
                    <div className="premium-card text-center space-y-6">
                        <div className="w-16 h-16 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center mx-auto">
                            <Mail size={24} />
                        </div>
                        <div className="space-y-2">
                            <h3 className="text-xl font-bold">Check your email</h3>
                            <p className="text-slate-500 text-sm">We've sent password reset instructions to <strong>{email}</strong></p>
                        </div>
                        <Button
                            className="w-full rounded-xl"
                            variant="outline"
                            onClick={() => navigate("/login")}
                        >
                            Return to Login
                        </Button>
                    </div>
                ) : (
                    <div className="premium-card">
                        <form className="space-y-6" onSubmit={handleSubmit}>
                            <div className="space-y-1">
                                <label htmlFor="email" className="block text-sm font-bold text-slate-900 ml-1">
                                    Email Address
                                </label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                        <Mail className="h-5 w-5 text-slate-400" />
                                    </div>
                                    <input
                                        id="email"
                                        name="email"
                                        type="email"
                                        autoComplete="email"
                                        required
                                        className="block w-full pl-11 pr-4 py-3 bg-surface-50 border border-line rounded-xl focus:ring-2 focus:ring-brand focus:border-transparent transition-all outline-none"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                    />
                                </div>
                            </div>

                            <Button
                                type="submit"
                                className="w-full text-white bg-brand hover:bg-brand-light rounded-xl h-12 gap-2"
                                disabled={loading}
                            >
                                {loading ? (
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    <>Send Reset Link <ArrowRight size={18} /></>
                                )}
                            </Button>
                        </form>
                    </div>
                )}

                <div className="text-center">
                    <button
                        onClick={() => navigate("/login")}
                        className="text-sm font-semibold text-brand hover:text-brand-light transition-colors flex items-center justify-center gap-1 mx-auto"
                    >
                        <ChevronLeft size={16} /> Back to Sign In
                    </button>
                </div>
            </div>
        </div>
    );
};

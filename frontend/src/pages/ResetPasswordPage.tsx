import React, { useState } from "react";
import { Lock, ArrowRight, ShieldCheck } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { request } from "../api/client";
import { useToast } from "../context/ToastContext";

export const ResetPasswordPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    const token = query.get("token");
    const { addToast } = useToast();

    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) {
            addToast("Invalid or missing reset token", "error");
            return;
        }

        if (password !== confirmPassword) {
            addToast("Passwords do not match", "error");
            return;
        }

        if (password.length < 8) {
            addToast("Password must be at least 8 characters", "error");
            return;
        }

        setLoading(true);
        try {
            await request("POST", "/auth/reset-password", { token, newPassword: password });
            setSuccess(true);
            addToast("Password reset successfully", "success");
        } catch (err: any) {
            addToast(err.message || "Failed to reset password", "error");
        } finally {
            setLoading(false);
        }
    };

    if (!token) {
        return (
            <div className="min-h-[80vh] flex flex-col items-center justify-center p-4">
                <div className="text-center space-y-4">
                    <h2 className="text-2xl font-bold">Invalid Link</h2>
                    <p className="text-slate-500">The password reset link is invalid or has expired.</p>
                    <Button onClick={() => navigate("/forgot-password")}>Request New Link</Button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-[80vh] flex flex-col items-center justify-center p-4">
            <div className="w-full max-w-md space-y-8 animate-fade-in">
                <div className="text-center">
                    <div className="w-16 h-16 bg-brand/10 text-brand rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-sm border border-brand/20">
                        <Lock size={32} />
                    </div>
                    <h2 className="text-3xl font-bold tracking-tight">Create New Password</h2>
                    <p className="mt-2 text-sm text-slate-500">
                        Please enter your new password below.
                    </p>
                </div>

                {success ? (
                    <div className="premium-card text-center space-y-6">
                        <div className="w-16 h-16 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center mx-auto">
                            <ShieldCheck size={24} />
                        </div>
                        <div className="space-y-2">
                            <h3 className="text-xl font-bold">Password Reset Complete</h3>
                            <p className="text-slate-500 text-sm">You can now sign in with your new password.</p>
                        </div>
                        <Button
                            className="w-full rounded-xl"
                            onClick={() => navigate("/login")}
                        >
                            Sign In
                        </Button>
                    </div>
                ) : (
                    <div className="premium-card">
                        <form className="space-y-6" onSubmit={handleSubmit}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-bold text-slate-900 ml-1 mb-1">
                                        New Password
                                    </label>
                                    <input
                                        type="password"
                                        required
                                        className="block w-full px-4 py-3 bg-surface-50 border border-line rounded-xl focus:ring-2 focus:ring-brand focus:border-transparent transition-all outline-none"
                                        placeholder="Min. 8 characters"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        minLength={8}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-bold text-slate-900 ml-1 mb-1">
                                        Confirm Password
                                    </label>
                                    <input
                                        type="password"
                                        required
                                        className="block w-full px-4 py-3 bg-surface-50 border border-line rounded-xl focus:ring-2 focus:ring-brand focus:border-transparent transition-all outline-none"
                                        placeholder="Confirm your new password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        minLength={8}
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
                                    <>Reset Password <ArrowRight size={18} /></>
                                )}
                            </Button>
                        </form>
                    </div>
                )}
            </div>
        </div>
    );
};

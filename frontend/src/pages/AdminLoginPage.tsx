import React, { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck, Lock, Mail, ArrowRight, KeyRound, AlertTriangle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";

type Step = "credentials" | "mfa";

const AdminLoginPage: React.FC = () => {
    const [step, setStep] = useState<Step>("credentials");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [otp, setOtp] = useState(["", "", "", "", "", ""]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const otpRefs = useRef<(HTMLInputElement | null)[]>([]);
    const navigate = useNavigate();
    const { loginAdmin } = useAuth();

    useEffect(() => {
        if (step === "mfa") {
            otpRefs.current[0]?.focus();
        }
    }, [step]);

    const handleCredentials = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        // Basic validation before hitting the API
        if (!email.trim() || !password.trim()) {
            setError("Please fill in all fields.");
            return;
        }

        // Move to MFA step
        setStep("mfa");
    };

    const handleOtpChange = (index: number, value: string) => {
        const digit = value.replace(/\D/g, "").slice(-1);
        const next = [...otp];
        next[index] = digit;
        setOtp(next);

        if (digit && index < 5) {
            otpRefs.current[index + 1]?.focus();
        }
    };

    const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === "Backspace" && !otp[index] && index > 0) {
            otpRefs.current[index - 1]?.focus();
        }
    };

    const handleOtpPaste = (e: React.ClipboardEvent) => {
        const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
        if (pasted.length === 6) {
            setOtp(pasted.split(""));
        }
        e.preventDefault();
    };

    const handleMfaSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const code = otp.join("");
        if (code.length !== 6) {
            setError("Please enter all 6 digits of your authenticator code.");
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            await loginAdmin(email, password, code);
            navigate("/admin");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Authentication failed");
            // Reset OTP on failure
            setOtp(["", "", "", "", "", ""]);
            otpRefs.current[0]?.focus();
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-4">
            {/* Background accent */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-violet-600/10 blur-[120px]" />
            </div>

            <div className="relative w-full max-w-md space-y-8 animate-fade-in">

                {/* Header */}
                <div className="text-center space-y-3">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-[20px] bg-violet-500/20 border border-violet-500/30 text-violet-400 mb-2">
                        <ShieldCheck size={32} />
                    </div>
                    <h1 className="text-3xl font-bold text-white">
                        {step === "credentials" ? "Admin Access" : "Verify Identity"}
                    </h1>
                    <p className="text-slate-400 text-sm">
                        {step === "credentials"
                            ? "Restricted area — authorized personnel only"
                            : `Enter the 6-digit code from your authenticator app for ${email}`}
                    </p>
                </div>

                {/* Card */}
                <div className="bg-slate-800/60 border border-slate-700/60 backdrop-blur-xl rounded-3xl p-8 shadow-2xl space-y-6">

                    {error && (
                        <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400">
                            <AlertTriangle size={18} className="shrink-0" />
                            <p className="text-sm font-medium">{error}</p>
                        </div>
                    )}

                    {/* Step 1: Credentials */}
                    {step === "credentials" && (
                        <form onSubmit={handleCredentials} className="space-y-5">
                            <div className="space-y-1">
                                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Email Address</label>
                                <div className="relative">
                                    <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="admin@example.com"
                                        required
                                        className="w-full bg-slate-900/60 border border-slate-700 rounded-2xl pl-11 pr-4 py-3.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 transition-all"
                                    />
                                </div>
                            </div>

                            <div className="space-y-1">
                                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Password</label>
                                <div className="relative">
                                    <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
                                    <input
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        placeholder="••••••••••"
                                        required
                                        className="w-full bg-slate-900/60 border border-slate-700 rounded-2xl pl-11 pr-4 py-3.5 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 transition-all"
                                    />
                                </div>
                            </div>

                            <button
                                type="submit"
                                className="w-full flex items-center justify-center gap-2 py-3.5 px-6 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-2xl transition-all duration-200 shadow-lg shadow-violet-900/40 hover:shadow-violet-700/40 text-sm"
                            >
                                Continue <ArrowRight size={16} />
                            </button>
                        </form>
                    )}

                    {/* Step 2: MFA */}
                    {step === "mfa" && (
                        <form onSubmit={handleMfaSubmit} className="space-y-6">
                            <div className="space-y-3">
                                <div className="flex items-center gap-2 mb-4">
                                    <KeyRound size={16} className="text-violet-400" />
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Authenticator Code</span>
                                </div>

                                {/* OTP Input Grid */}
                                <div className="flex gap-3 justify-center" onPaste={handleOtpPaste}>
                                    {otp.map((digit, i) => (
                                        <input
                                            key={i}
                                            ref={(el) => { otpRefs.current[i] = el; }}
                                            type="text"
                                            inputMode="numeric"
                                            maxLength={1}
                                            value={digit}
                                            onChange={(e) => handleOtpChange(i, e.target.value)}
                                            onKeyDown={(e) => handleOtpKeyDown(i, e)}
                                            className={`w-12 h-14 text-center text-xl font-bold rounded-2xl border transition-all duration-150 bg-slate-900/60 text-white focus:outline-none
                                                ${digit
                                                    ? "border-violet-500 bg-violet-500/10 text-violet-300"
                                                    : "border-slate-700 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20"
                                                }`}
                                        />
                                    ))}
                                </div>
                                <p className="text-center text-xs text-slate-500 mt-2">
                                    Open your authenticator app and enter the current 6-digit code
                                </p>
                            </div>

                            <button
                                type="submit"
                                disabled={isLoading || otp.join("").length !== 6}
                                className="w-full flex items-center justify-center gap-2 py-3.5 px-6 bg-violet-600 hover:bg-violet-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-2xl transition-all duration-200 shadow-lg shadow-violet-900/40 hover:shadow-violet-700/40 text-sm"
                            >
                                {isLoading ? (
                                    <span className="flex items-center gap-2">
                                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        Verifying…
                                    </span>
                                ) : (
                                    <>Verify & Access Dashboard <ShieldCheck size={16} /></>
                                )}
                            </button>

                            <button
                                type="button"
                                onClick={() => { setStep("credentials"); setError(null); setOtp(["", "", "", "", "", ""]); }}
                                className="w-full text-xs text-slate-500 hover:text-slate-300 transition-colors py-1"
                            >
                                ← Go back and change credentials
                            </button>
                        </form>
                    )}
                </div>

                {/* Footer note */}
                <p className="text-center text-xs text-slate-600">
                    Regular user?{" "}
                    <a href="/login" className="text-slate-400 hover:text-white transition-colors underline underline-offset-2">
                        Sign in here
                    </a>
                </p>
            </div>
        </div>
    );
};

export { AdminLoginPage };

import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, AlertCircle, Info, X, AlertTriangle } from "lucide-react";

interface ToastProps {
    message: string;
    type: "success" | "error" | "info" | "warning";
    onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type, onClose }) => {
    const config = {
        success: {
            icon: CheckCircle2,
            bg: "bg-emerald-50 text-emerald-800 border-emerald-200",
            iconColor: "text-emerald-500"
        },
        error: {
            icon: AlertCircle,
            bg: "bg-red-50 text-red-800 border-red-200",
            iconColor: "text-red-500"
        },
        warning: {
            icon: AlertTriangle,
            bg: "bg-amber-50 text-amber-800 border-amber-200",
            iconColor: "text-amber-500"
        },
        info: {
            icon: Info,
            bg: "bg-blue-50 text-blue-800 border-blue-200",
            iconColor: "text-blue-500"
        }
    };

    const { icon: Icon, bg, iconColor } = config[type];

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            className={`flex items-center gap-3 p-4 w-72 md:w-80 rounded-2xl shadow-premium border backdrop-blur-md pointer-events-auto ${bg}`}
        >
            <Icon className={`shrink-0 ${iconColor}`} size={20} />
            <p className="text-sm font-medium flex-1 mr-2">{message}</p>
            <button
                onClick={onClose}
                className="p-1 hover:bg-black/5 rounded-lg transition-colors shrink-0"
            >
                <X size={16} className="opacity-70" />
            </button>
        </motion.div>
    );
};

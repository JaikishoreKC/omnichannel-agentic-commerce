import React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../utils/cn";

const badgeVariants = cva(
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2",
    {
        variants: {
            variant: {
                default: "border-transparent bg-brand text-white",
                secondary: "border-transparent bg-surface-100 text-ink",
                outline: "text-ink border border-line",
                success: "border-transparent bg-emerald-500 text-white",
                warning: "border-transparent bg-amber-500 text-white",
                danger: "border-transparent bg-red-500 text-white",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
);

export interface BadgeProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> { }

function Badge({ className, variant, ...props }: BadgeProps) {
    return (
        <div className={cn(badgeVariants({ variant }), className)} {...props} />
    );
}

export { Badge };

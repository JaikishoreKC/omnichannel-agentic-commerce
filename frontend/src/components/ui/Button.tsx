import React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../utils/cn";
import { Loader2 } from "lucide-react";

// I need to install class-variance-authority as well for a truly premium component experience
const buttonVariants = cva(
    "inline-flex items-center justify-center rounded-xl text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]",
    {
        variants: {
            variant: {
                primary: "bg-brand text-white hover:bg-brand-dark shadow-sm",
                secondary: "bg-surface-100 text-ink hover:bg-surface-200 border border-line",
                accent: "bg-accent text-white hover:bg-accent-dark shadow-sm",
                ghost: "hover:bg-surface-100 text-ink",
                outline: "border border-line bg-transparent hover:bg-surface-50 text-ink",
                danger: "bg-red-500 text-white hover:bg-red-600",
            },
            size: {
                sm: "h-9 px-3 rounded-lg",
                md: "h-11 px-6 rounded-xl",
                lg: "h-14 px-8 rounded-2xl text-base",
                icon: "h-10 w-10",
            },
        },
        defaultVariants: {
            variant: "primary",
            size: "md",
        },
    }
);

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    isLoading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, isLoading, children, ...props }, ref) => {
        return (
            <button
                className={cn(buttonVariants({ variant, size, className }))}
                ref={ref}
                disabled={isLoading || props.disabled}
                {...props}
            >
                {isLoading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                {children}
            </button>
        );
    }
);
Button.displayName = "Button";

export { Button };

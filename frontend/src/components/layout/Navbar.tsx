import React from "react";
import { Link, useLocation } from "react-router-dom";
import { ShoppingBag, User, Search, MessageSquare, Menu, Shield } from "lucide-react";
import { cn } from "../../utils/cn";
import { useCart } from "../../context/CartContext";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";

const Navbar: React.FC = () => {
    const location = useLocation();
    const { cart } = useCart();
    const { user } = useAuth();

    const navLinks = [
        { label: "Home", href: "/" },
        { label: "Shop", href: "/products" },
    ];

    return (
        <header className="fixed top-0 left-0 right-0 z-40 px-4 pt-4 pointer-events-none">
            <nav className="max-w-7xl mx-auto h-16 glass rounded-2xl px-6 flex items-center justify-between pointer-events-auto">
                <div className="flex items-center gap-8">
                    <Link to="/" className="text-2xl font-display font-bold tracking-tight text-brand">
                        AGENTIC<span className="text-ink">.</span>
                    </Link>

                    <div className="hidden md:flex items-center gap-6">
                        {navLinks.map((link) => (
                            <Link
                                key={link.href}
                                to={link.href}
                                className={cn(
                                    "text-sm font-medium transition-colors hover:text-brand",
                                    location.pathname === link.href ? "text-brand" : "text-slate-500"
                                )}
                            >
                                {link.label}
                            </Link>
                        ))}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <Button variant="ghost" size="icon" className="md:hidden">
                        <Menu size={20} />
                    </Button>

                    <Button variant="ghost" size="icon">
                        <Link to="/products">
                            <Search size={20} />
                        </Link>
                    </Button>

                    <Link to="/cart" className="relative" data-testid="cart-link">
                        <Button variant="ghost" size="icon">
                            <ShoppingBag size={20} />
                            {cart && cart.itemCount > 0 && (
                                <span
                                    className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-accent text-[10px] font-bold text-white"
                                    data-testid="cart-item-count"
                                >
                                    {cart.itemCount}
                                </span>
                            )}
                        </Button>
                    </Link>

                    <div className="w-px h-6 bg-line mx-1" />

                    {user ? (
                        <div className="flex items-center gap-2">
                            {user.role === "admin" && (
                                <Link to="/admin" data-testid="admin-dashboard-link">
                                    <Button variant="secondary" size="sm" className="gap-2 rounded-full px-4 bg-violet-100 text-violet-700 hover:bg-violet-200 border-violet-200">
                                        <Shield size={14} /> Admin
                                    </Button>
                                </Link>
                            )}
                            <Link to="/account" data-testid="user-account-link">
                                <Button variant="secondary" size="sm" className="gap-2 rounded-full px-4">
                                    <User size={16} />
                                    <span className="hidden sm:inline">{user.name.split(" ")[0]}</span>
                                </Button>
                            </Link>
                        </div>
                    ) : (
                        <Link to="/login" data-testid="login-link">
                            <Button size="sm" className="rounded-full px-6">
                                Sign In
                            </Button>
                        </Link>
                    )}
                </div>
            </nav>
        </header>
    );
};

export { Navbar };

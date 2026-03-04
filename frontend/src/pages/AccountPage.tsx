import React, { useEffect, useState } from "react";
import { User, LogOut, Package, Shield, ExternalLink, QrCode, Clock, CheckCircle2, Truck, AlertCircle, BrainCircuit, LifeBuoy, Heart, Settings } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useNavigate } from "react-router-dom";
import { fetchOrders } from "../api";
import type { Order } from "../types";
import { cn } from "../utils/cn";
import { AiMemoryTab } from "../components/account/AiMemoryTab";
import { SupportTicketsTab } from "../components/account/SupportTicketsTab";
import { WishlistTab } from "../components/account/WishlistTab";

const AccountPage: React.FC = () => {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState("orders");
    const [orders, setOrders] = useState<Order[]>([]);
    const [isLoadingOrders, setIsLoadingOrders] = useState(true);

    useEffect(() => {
        const load = async () => {
            try {
                const data = await fetchOrders();
                setOrders(data);
            } catch {
                setOrders([]);
            } finally {
                setIsLoadingOrders(false);
            }
        };
        load();
    }, []);

    type AccountTab = "orders" | "memory" | "support" | "wishlist" | "settings";
    const tabs: Array<{ id: AccountTab; label: string; icon: React.ElementType }> = [
        { id: "orders", label: "Orders", icon: Package },
        { id: "memory", label: "AI Memory", icon: BrainCircuit },
        { id: "support", label: "Support", icon: LifeBuoy },
        { id: "wishlist", label: "Wishlist", icon: Heart },
        { id: "settings", label: "Settings", icon: Settings },
    ];

    if (!user) {
        navigate("/login");
        return null;
    }

    const handleLogout = () => {
        logout();
        navigate("/");
    };

    const getStatusIcon = (status: string) => {
        switch (status.toLowerCase()) {
            case "confirmed": return <CheckCircle2 size={16} className="text-emerald-500" />;
            case "processing": return <Clock size={16} className="text-amber-500" />;
            case "shipped": return <Truck size={16} className="text-blue-500" />;
            case "delivered": return <CheckCircle2 size={16} className="text-emerald-500" />;
            default: return <AlertCircle size={16} className="text-slate-400" />;
        }
    };

    const sections = [
        {
            title: "Active Channels",
            icon: ExternalLink,
            content: (
                <div className="space-y-4">
                    <p className="text-sm text-slate-500">Linked platforms for omnichannel notifications.</p>
                    <div className="flex flex-wrap gap-3">
                        <Badge variant="secondary" className="px-4 py-2 rounded-xl gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Web (Current)
                        </Badge>
                        <Button variant="outline" size="sm" className="rounded-xl border-dashed">
                            + Link Telegram
                        </Button>
                    </div>
                </div>
            )
        },
        {
            title: "Security (MFA)",
            icon: Shield,
            content: (
                <div className="space-y-4">
                    <p className="text-sm text-slate-500">Manage your Multi-Factor Authentication settings.</p>
                    <div className="p-4 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <QrCode className="text-amber-600" size={24} />
                            <div>
                                <div className="font-bold text-amber-900 text-sm">TOTP Verification</div>
                                <div className="text-xs text-amber-700">Scan QR to sync with Authenticator app</div>
                            </div>
                        </div>
                        <Button variant="secondary" size="sm" className="bg-white border-amber-200 text-amber-900">
                            Configure
                        </Button>
                    </div>
                </div>
            )
        }
    ];

    return (
        <div className="max-w-4xl mx-auto space-y-12 animate-fade-in">
            {/* Profile Header */}
            <div className="flex flex-col md:flex-row items-center gap-8 md:items-start text-center md:text-left">
                <div className="w-24 h-24 rounded-[32px] bg-brand/10 text-brand flex items-center justify-center border-2 border-brand/20">
                    <User size={48} />
                </div>
                <div className="flex-1 space-y-4">
                    <div className="space-y-1">
                        <h1 className="text-4xl font-bold">{user.name}</h1>
                        <p className="text-slate-500">{user.email}</p>
                    </div>
                    <div className="flex flex-wrap items-center justify-center md:justify-start gap-3">
                        <Badge variant="default" className="rounded-lg">{user.role}</Badge>
                        <span className="text-xs text-slate-400 font-medium tracking-wider uppercase">Joined {new Date(user.createdAt).toLocaleDateString()}</span>
                    </div>
                </div>
                <Button variant="danger" size="sm" onClick={handleLogout} className="rounded-xl gap-2">
                    <LogOut size={16} /> Sign Out
                </Button>
            </div>

            {/* Navigation Tabs */}
            <div className="flex overflow-x-auto gap-2 pb-2 scrollbar-hide">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "flex items-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm whitespace-nowrap transition-colors",
                            activeTab === tab.id
                                ? "bg-brand text-white shadow-md shadow-brand/20"
                                : "bg-white text-slate-500 hover:text-slate-900 border border-line"
                        )}
                    >
                        <tab.icon size={16} /> {tab.label}
                    </button>
                ))}
            </div>

            {/* Content Area */}
            {activeTab === "orders" && (
                <div className="premium-card animate-fade-in">
                    <div className="flex items-center justify-between mb-8">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-600">
                                <Package size={20} />
                            </div>
                            <h3 className="text-lg font-bold">Recent Orders</h3>
                        </div>
                        {orders.length > 0 && <Button variant="ghost" size="sm" className="text-brand font-bold h-auto py-0 px-2">View All</Button>}
                    </div>

                    {isLoadingOrders ? (
                        <div className="py-12 flex flex-col items-center justify-center space-y-4">
                            <div className="animate-spin w-8 h-8 border-4 border-brand border-t-transparent rounded-full" />
                            <p className="text-slate-400 text-sm">Getting your orders...</p>
                        </div>
                    ) : orders.length > 0 ? (
                        <div className="divide-y divide-line">
                            {orders.map((order) => (
                                <div key={order.id} className="py-6 first:pt-0 last:pb-0 flex flex-col sm:flex-row items-center justify-between gap-6">
                                    <div className="space-y-1 text-center sm:text-left">
                                        <div className="flex items-center gap-2 justify-center sm:justify-start">
                                            <span className="font-bold text-slate-900">#{order.id.slice(0, 8).toUpperCase()}</span>
                                            <Badge variant="secondary" className="gap-1.5 py-0.5 px-2 rounded-lg text-[10px] uppercase tracking-wider">
                                                {getStatusIcon(order.status)}
                                                {order.status}
                                            </Badge>
                                        </div>
                                        <div className="text-xs text-slate-400">
                                            {new Date(order.createdAt).toLocaleDateString()} at {new Date(order.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-8">
                                        <div className="text-right">
                                            <div className="text-sm font-bold text-slate-900">${order.total.toFixed(2)}</div>
                                            <div className="text-[10px] text-slate-400 uppercase tracking-widest font-medium">{order.itemCount} items</div>
                                        </div>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="rounded-xl h-9 px-4"
                                            onClick={() => navigate(`/account/orders/${order.id}`)}
                                        >
                                            Details
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 text-center space-y-4 border-2 border-dashed border-line rounded-3xl bg-surface-50">
                            <p className="text-sm text-slate-400">You haven't placed any orders yet.</p>
                            <Button variant="outline" size="sm" onClick={() => navigate("/products")} className="rounded-xl">
                                Browse Products
                            </Button>
                        </div>
                    )}
                </div>
            )}

            {activeTab === "memory" && <AiMemoryTab />}
            {activeTab === "support" && <SupportTicketsTab />}
            {activeTab === "wishlist" && <WishlistTab />}

            {activeTab === "settings" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-fade-in">
                    {sections.map((section, idx) => (
                        <div key={idx} className="premium-card space-y-6">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-surface-100 flex items-center justify-center text-slate-600">
                                    <section.icon size={20} />
                                </div>
                                <h3 className="text-lg font-bold">{section.title}</h3>
                            </div>
                            {section.content}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export { AccountPage };

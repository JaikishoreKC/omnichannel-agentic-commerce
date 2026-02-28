import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Users, Package, ShoppingCart, TrendingUp, Plus, Activity,
    Shield, LogOut, RefreshCw, CheckCircle2, AlertCircle,
    Clock, ChevronRight, Boxes, BarChart3, List
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getAdminStats, getAdminOrders, getAdminProducts, getAdminUsers, getActivityLogs } from "../api/admin";
import type { AdminStats, AdminOrder, AdminProduct, AdminUser, ActivityLog } from "../api/admin";

// ─── Sub-nav tabs ────────────────────────────────────────────────────────────
type Tab = "overview" | "orders" | "products" | "users" | "activity";

// ─── Status badge ─────────────────────────────────────────────────────────────
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const map: Record<string, { label: string; cls: string }> = {
        confirmed: { label: "Confirmed", cls: "bg-blue-100 text-blue-700" },
        shipped: { label: "Shipped", cls: "bg-indigo-100 text-indigo-700" },
        delivered: { label: "Delivered", cls: "bg-emerald-100 text-emerald-700" },
        cancelled: { label: "Cancelled", cls: "bg-red-100 text-red-700" },
        pending: { label: "Pending", cls: "bg-amber-100 text-amber-700" },
        refunded: { label: "Refunded", cls: "bg-slate-100 text-slate-600" },
        active: { label: "Active", cls: "bg-emerald-100 text-emerald-700" },
        admin: { label: "Admin", cls: "bg-violet-100 text-violet-700" },
        customer: { label: "Customer", cls: "bg-sky-100 text-sky-700" },
    };
    const s = map[status?.toLowerCase()] ?? { label: status, cls: "bg-slate-100 text-slate-600" };
    return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-semibold ${s.cls}`}>{s.label}</span>;
};

// ─── Loading skeleton ──────────────────────────────────────────────────────────
const Skeleton: React.FC<{ className?: string }> = ({ className = "" }) => (
    <div className={`animate-pulse bg-slate-100 rounded-xl ${className}`} />
);

// ─── Main component ────────────────────────────────────────────────────────────
const AdminDashboard: React.FC = () => {
    const { user, logout, isAdmin } = useAuth();
    const navigate = useNavigate();

    const [activeTab, setActiveTab] = useState<Tab>("overview");
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [orders, setOrders] = useState<AdminOrder[]>([]);
    const [products, setProducts] = useState<AdminProduct[]>([]);
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [logs, setLogs] = useState<ActivityLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [integrity, setIntegrity] = useState<{ ok: boolean; total: number } | null>(null);

    // Guard: only admin can see this
    useEffect(() => {
        if (!user) { navigate("/admin/login"); return; }
        if (!isAdmin) { navigate("/"); return; }
    }, [user, isAdmin, navigate]);

    const loadData = async (silent = false) => {
        if (!silent) setLoading(true);
        else setRefreshing(true);
        setError(null);
        try {
            const [s, o, p, u, l] = await Promise.allSettled([
                getAdminStats(),
                getAdminOrders(10),
                getAdminProducts(20),
                getAdminUsers(20),
                getActivityLogs(20),
            ]);
            if (s.status === "fulfilled") setStats(s.value);
            if (o.status === "fulfilled") setOrders(o.value);
            if (p.status === "fulfilled") setProducts(p.value);
            if (u.status === "fulfilled") setUsers(u.value);
            if (l.status === "fulfilled") setLogs(l.value);
        } catch {
            setError("Failed to load admin data. Check your connection.");
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { loadData(); }, []);

    const handleLogout = () => { logout(); navigate("/admin/login"); };

    const statCards = stats ? [
        { label: "Total Revenue", value: `$${stats.totalRevenue.toLocaleString("en-US", { minimumFractionDigits: 2 })}`, icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50" },
        { label: "Registered Users", value: stats.activeUsers.toLocaleString(), icon: Users, color: "text-blue-600", bg: "bg-blue-50" },
        { label: "Pending Orders", value: stats.pendingOrders.toLocaleString(), icon: ShoppingCart, color: "text-amber-600", bg: "bg-amber-50" },
        { label: "Total Products", value: stats.totalProducts.toLocaleString(), icon: Package, color: "text-violet-600", bg: "bg-violet-50" },
    ] : [];

    const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
        { id: "overview", label: "Overview", icon: BarChart3 },
        { id: "orders", label: "Orders", icon: ShoppingCart },
        { id: "products", label: "Products", icon: Boxes },
        { id: "users", label: "Users", icon: Users },
        { id: "activity", label: "Activity Log", icon: List },
    ];

    if (!user || !isAdmin) return null;

    return (
        <div className="min-h-screen bg-slate-50">

            {/* Admin-specific top bar — no shared Navbar */}
            <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-40 shadow-sm">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-xl bg-violet-600 flex items-center justify-center">
                                <Shield size={16} className="text-white" />
                            </div>
                            <span className="text-lg font-bold text-slate-900">Admin Center</span>
                        </div>

                        {/* Tabs */}
                        <nav className="hidden md:flex items-center gap-1 ml-8">
                            {tabs.map(tab => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all
                                        ${activeTab === tab.id
                                            ? "bg-violet-100 text-violet-700"
                                            : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                                        }`}
                                >
                                    <tab.icon size={14} /> {tab.label}
                                </button>
                            ))}
                        </nav>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => loadData(true)}
                            disabled={refreshing}
                            className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-all"
                        >
                            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
                            Refresh
                        </button>
                        <div className="flex items-center gap-2 px-3 py-2 bg-violet-50 rounded-xl">
                            <div className="w-6 h-6 rounded-lg bg-violet-200 flex items-center justify-center">
                                <Shield size={12} className="text-violet-700" />
                            </div>
                            <span className="text-xs font-semibold text-violet-700">{user.name}</span>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-red-500 hover:bg-red-50 rounded-xl transition-all"
                        >
                            <LogOut size={14} /> Sign Out
                        </button>
                    </div>
                </div>
            </header>

            {/* Mobile tabs */}
            <div className="md:hidden overflow-x-auto bg-white border-b border-slate-200 px-4">
                <div className="flex gap-1 py-2">
                    {tabs.map(tab => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-1 px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-all
                                ${activeTab === tab.id ? "bg-violet-100 text-violet-700" : "text-slate-500 hover:bg-slate-100"}`}
                        >
                            <tab.icon size={12} /> {tab.label}
                        </button>
                    ))}
                </div>
            </div>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">

                {/* Error banner */}
                {error && (
                    <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700">
                        <AlertCircle size={18} className="shrink-0" />
                        <span className="text-sm font-medium">{error}</span>
                    </div>
                )}

                {/* ── OVERVIEW ─────────────────────────────────────────── */}
                {activeTab === "overview" && (
                    <div className="space-y-8 animate-fade-in">
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>
                            <p className="text-slate-500 text-sm mt-1">Live platform metrics and system status</p>
                        </div>

                        {/* Stats grid */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                            {loading
                                ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-32" />)
                                : statCards.map((card, i) => (
                                    <div key={i} className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm hover:shadow-md transition-shadow">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className={`w-10 h-10 rounded-xl ${card.bg} ${card.color} flex items-center justify-center`}>
                                                <card.icon size={20} />
                                            </div>
                                        </div>
                                        <div>
                                            <p className="text-sm text-slate-500 font-medium">{card.label}</p>
                                            <h3 className="text-2xl font-bold text-slate-900 mt-1">{card.value}</h3>
                                        </div>
                                    </div>
                                ))}
                        </div>

                        {/* Recent orders */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/80 shadow-sm">
                                <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-slate-100">
                                    <h2 className="font-bold text-slate-900">Recent Orders</h2>
                                    <button onClick={() => setActiveTab("orders")} className="text-xs font-medium text-violet-600 hover:text-violet-800 flex items-center gap-1">
                                        View all <ChevronRight size={12} />
                                    </button>
                                </div>
                                <div className="overflow-x-auto">
                                    {loading ? (
                                        <div className="p-6 space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
                                    ) : orders.length === 0 ? (
                                        <div className="p-8 text-center text-slate-400 text-sm">No orders yet</div>
                                    ) : (
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="text-xs uppercase tracking-wider text-slate-400 border-b border-slate-100">
                                                    <th className="text-left py-3 px-6">Order</th>
                                                    <th className="text-left py-3 px-4">Status</th>
                                                    <th className="text-right py-3 px-6">Total</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {orders.slice(0, 6).map((o) => (
                                                    <tr key={o.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                        <td className="py-3.5 px-6">
                                                            <span className="font-mono text-xs text-slate-500">#{o.id.slice(-8).toUpperCase()}</span>
                                                        </td>
                                                        <td className="py-3.5 px-4"><StatusBadge status={o.status} /></td>
                                                        <td className="py-3.5 px-6 text-right font-semibold text-slate-800">
                                                            ${(o.total ?? 0).toFixed(2)}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    )}
                                </div>
                            </div>

                            {/* Integrity check */}
                            <div className="space-y-5">
                                <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-4">
                                    <h2 className="font-bold text-slate-900">Activity Integrity</h2>
                                    <p className="text-xs text-slate-500">Hash-chain tamper verification on admin action logs.</p>
                                    {integrity ? (
                                        <div className={`flex items-center gap-3 p-3 rounded-xl ${integrity.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                                            {integrity.ok ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                                            <div>
                                                <p className="font-bold text-sm">{integrity.ok ? "Verified" : "Tampering Detected"}</p>
                                                <p className="text-xs mt-0.5">{integrity.total} records checked</p>
                                            </div>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={async () => {
                                                try {
                                                    const { verifyAdminIntegrity } = await import("../api/admin");
                                                    const r = await verifyAdminIntegrity();
                                                    setIntegrity(r);
                                                } catch {
                                                    setIntegrity({ ok: false, total: 0 });
                                                }
                                            }}
                                            className="w-full py-2.5 text-xs font-semibold rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                                        >
                                            Run Integrity Check
                                        </button>
                                    )}
                                </div>

                                <div className="bg-violet-600 rounded-2xl p-6 text-white shadow-sm">
                                    <h3 className="font-bold text-sm mb-1">Quick Actions</h3>
                                    <p className="text-xs text-violet-200 mb-4">Manage your store</p>
                                    <div className="space-y-2">
                                        <button onClick={() => setActiveTab("products")} className="w-full flex items-center gap-2 py-2 px-3 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-medium transition-colors">
                                            <Plus size={12} /> Add New Product
                                        </button>
                                        <button onClick={() => setActiveTab("activity")} className="w-full flex items-center gap-2 py-2 px-3 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-medium transition-colors">
                                            <Activity size={12} /> View Activity Log
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── ORDERS ───────────────────────────────────────────── */}
                {activeTab === "orders" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">All Orders</h1>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : orders.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No orders found</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Order ID</th>
                                            <th className="text-left py-3.5 px-4">Customer</th>
                                            <th className="text-left py-3.5 px-4">Items</th>
                                            <th className="text-left py-3.5 px-4">Status</th>
                                            <th className="text-right py-3.5 px-6">Total</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {orders.map((o) => (
                                            <tr key={o.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 font-mono text-xs text-slate-500">#{o.id.slice(-10).toUpperCase()}</td>
                                                <td className="py-4 px-4 text-xs text-slate-600">{o.userId.slice(0, 12)}…</td>
                                                <td className="py-4 px-4 text-xs text-slate-500">{o.items?.length ?? 0} item(s)</td>
                                                <td className="py-4 px-4"><StatusBadge status={o.status} /></td>
                                                <td className="py-4 px-6 text-right font-bold text-slate-800">${(o.total ?? 0).toFixed(2)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

                {/* ── PRODUCTS ─────────────────────────────────────────── */}
                {activeTab === "products" && (
                    <div className="space-y-6 animate-fade-in">
                        <div className="flex items-center justify-between">
                            <h1 className="text-2xl font-bold text-slate-900">Products ({products.length})</h1>
                            <button className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 text-white text-sm font-semibold rounded-xl hover:bg-violet-700 transition-colors shadow-sm">
                                <Plus size={16} /> Add Product
                            </button>
                        </div>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : products.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No products found</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Name</th>
                                            <th className="text-left py-3.5 px-4">Category</th>
                                            <th className="text-left py-3.5 px-4">Variants</th>
                                            <th className="text-right py-3.5 px-6">Price</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {products.map((p) => (
                                            <tr key={p.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 font-medium text-slate-800">{p.name}</td>
                                                <td className="py-4 px-4 text-xs"><StatusBadge status={p.category} /></td>
                                                <td className="py-4 px-4 text-xs text-slate-500">{p.variants?.length ?? 0} variant(s)</td>
                                                <td className="py-4 px-6 text-right font-bold text-slate-700">${p.price.toFixed(2)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

                {/* ── USERS ────────────────────────────────────────────── */}
                {activeTab === "users" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">All Users ({users.length})</h1>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : users.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No users found</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Name</th>
                                            <th className="text-left py-3.5 px-4">Email</th>
                                            <th className="text-left py-3.5 px-4">Role</th>
                                            <th className="text-left py-3.5 px-4">Joined</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map((u) => (
                                            <tr key={u.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 font-medium text-slate-800">{u.name}</td>
                                                <td className="py-4 px-4 text-xs text-slate-500">{u.email}</td>
                                                <td className="py-4 px-4"><StatusBadge status={u.role} /></td>
                                                <td className="py-4 px-4 text-xs text-slate-500">
                                                    {u.createdAt ? new Date(u.createdAt).toLocaleDateString() : "—"}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

                {/* ── ACTIVITY LOG ──────────────────────────────────────── */}
                {activeTab === "activity" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">Admin Activity Log</h1>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : logs.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No activity logs yet</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Admin</th>
                                            <th className="text-left py-3.5 px-4">Action</th>
                                            <th className="text-left py-3.5 px-4">Resource</th>
                                            <th className="text-left py-3.5 px-4">Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {logs.map((log) => (
                                            <tr key={log.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 text-xs text-slate-600">{log.adminEmail}</td>
                                                <td className="py-4 px-4">
                                                    <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-lg">{log.action}</span>
                                                </td>
                                                <td className="py-4 px-4 text-xs text-slate-500">{log.resource}/{log.resourceId?.slice(0, 8)}</td>
                                                <td className="py-4 px-4 text-xs text-slate-400 flex items-center gap-1">
                                                    <Clock size={11} />
                                                    {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

            </main>
        </div>
    );
};

export { AdminDashboard };

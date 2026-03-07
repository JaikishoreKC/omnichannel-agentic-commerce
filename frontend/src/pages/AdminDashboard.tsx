import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    Users, Package, ShoppingCart, TrendingUp, Plus, Activity,
    Shield, LogOut, RefreshCw, CheckCircle2, AlertCircle,
    Clock, ChevronRight, Boxes, BarChart3, List, Sparkles, PhoneCall, LifeBuoy, Tags, Warehouse
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
    getAdminStats,
    getAdminOrders,
    getAdminProducts,
    createProduct,
    deleteProduct,
    getAdminUsers,
    getActivityLogs,
    getHealth,
    verifyAdminIntegrity,
    getAdminSupportTickets,
    updateAdminSupportTicket,
    getVoiceSettings,
    updateVoiceSettings,
    runVoiceRecoveryProcess,
    getVoiceCalls,
    getVoiceJobs,
    getVoiceStats,
    getAdminCategories,
    createAdminCategory,
    updateAdminCategory,
    deleteAdminCategory,
    getAdminInventory,
    updateAdminInventory,
} from "../api/admin";
import type {
    AdminStats,
    AdminOrder,
    AdminProduct,
    AdminUser,
    ActivityLog,
    HealthStatus,
    AdminSupportTicket,
    VoiceSettings,
    VoiceCall,
    VoiceJob,
    VoiceStats,
    AdminCategory,
    AdminInventory,
} from "../api/admin";
import { useToast } from "../context/ToastContext";
import { Input } from "../components/ui/Input";

// ─── Sub-nav tabs ────────────────────────────────────────────────────────────
type Tab = "overview" | "orders" | "products" | "users" | "activity" | "support" | "voice" | "categories" | "inventory";

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
    const { addToast } = useToast();
    const navigate = useNavigate();

    const [activeTab, setActiveTab] = useState<Tab>("overview");
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [orders, setOrders] = useState<AdminOrder[]>([]);
    const [products, setProducts] = useState<AdminProduct[]>([]);
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [logs, setLogs] = useState<ActivityLog[]>([]);
    const [health, setHealth] = useState<HealthStatus | null>(null);
    const [supportTickets, setSupportTickets] = useState<AdminSupportTicket[]>([]);
    const [voiceSettings, setVoiceSettings] = useState<VoiceSettings | null>(null);
    const [voiceCalls, setVoiceCalls] = useState<VoiceCall[]>([]);
    const [voiceJobs, setVoiceJobs] = useState<VoiceJob[]>([]);
    const [voiceStats, setVoiceStats] = useState<VoiceStats | null>(null);
    const [categories, setCategories] = useState<AdminCategory[]>([]);
    const [inventory, setInventory] = useState<AdminInventory | null>(null);
    const [selectedProductId, setSelectedProductId] = useState<string>("");
    const [selectedVariantId, setSelectedVariantId] = useState<string>("");
    const [inventoryTotal, setInventoryTotal] = useState<string>("");
    const [inventoryAvailable, setInventoryAvailable] = useState<string>("");
    const [newCategoryName, setNewCategoryName] = useState("");
    const [newCategorySlug, setNewCategorySlug] = useState("");
    const [newCategoryDescription, setNewCategoryDescription] = useState("");
    const [newProductName, setNewProductName] = useState("");
    const [newProductDescription, setNewProductDescription] = useState("");
    const [newProductCategory, setNewProductCategory] = useState("");
    const [newProductPrice, setNewProductPrice] = useState("");
    const [showProductForm, setShowProductForm] = useState(false);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [integrity, setIntegrity] = useState<{ ok: boolean; total: number } | null>(null);
    const [tabActionError, setTabActionError] = useState<string | null>(null);
    const [actionBusyKey, setActionBusyKey] = useState<string | null>(null);

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
            const [s, o, p, u, l, h, st, vs, vc, vj, vst, cat] = await Promise.allSettled([
                getAdminStats(),
                getAdminOrders(10),
                getAdminProducts(20),
                getAdminUsers(20),
                getActivityLogs(20),
                getHealth(),
                getAdminSupportTickets({ limit: 20 }),
                getVoiceSettings(),
                getVoiceCalls(20),
                getVoiceJobs(20),
                getVoiceStats(),
                getAdminCategories(),
            ]);
            if (s.status === "fulfilled") setStats(s.value);
            if (o.status === "fulfilled") setOrders(o.value);
            if (p.status === "fulfilled") setProducts(p.value);
            if (u.status === "fulfilled") setUsers(u.value);
            if (l.status === "fulfilled") setLogs(l.value);
            if (h.status === "fulfilled") setHealth(h.value);
            if (st.status === "fulfilled") setSupportTickets(st.value);
            if (vs.status === "fulfilled") setVoiceSettings(vs.value);
            if (vc.status === "fulfilled") setVoiceCalls(vc.value);
            if (vj.status === "fulfilled") setVoiceJobs(vj.value);
            if (vst.status === "fulfilled") setVoiceStats(vst.value);
            if (cat.status === "fulfilled") setCategories(cat.value);
        } catch {
            setError("Failed to load admin data. Check your connection.");
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => { loadData(); }, []);
    useEffect(() => { setTabActionError(null); }, [activeTab]);

    const handleLogout = async () => {
        await logout();
        navigate("/admin/login");
    };

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
        { id: "support", label: "Support", icon: LifeBuoy },
        { id: "voice", label: "Voice", icon: PhoneCall },
        { id: "categories", label: "Categories", icon: Tags },
        { id: "inventory", label: "Inventory", icon: Warehouse },
    ];

    const selectedProduct = products.find((product) => product.id === selectedProductId) ?? null;

    const handleCreateCategory = async () => {
        if (!newCategoryName.trim()) {
            addToast("Category name is required", "warning");
            return;
        }
        setActionBusyKey("category-create");
        setTabActionError(null);
        try {
            await createAdminCategory({
                name: newCategoryName.trim(),
                slug: newCategorySlug.trim() || undefined,
                description: newCategoryDescription.trim() || undefined,
                status: "active",
            });
            addToast("Category created", "success");
            setNewCategoryName("");
            setNewCategorySlug("");
            setNewCategoryDescription("");
            setCategories(await getAdminCategories());
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to create category";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleCreateProduct = async () => {
        const name = newProductName.trim();
        const category = newProductCategory.trim().toLowerCase();
        const price = Number(newProductPrice);
        if (!name) {
            addToast("Product name is required", "warning");
            return;
        }
        if (!category) {
            addToast("Category is required", "warning");
            return;
        }
        if (!Number.isFinite(price) || price <= 0) {
            addToast("Price must be greater than 0", "warning");
            return;
        }

        setActionBusyKey("product-create");
        setTabActionError(null);
        try {
            await createProduct({
                name,
                description: newProductDescription.trim(),
                category,
                price,
                currency: "USD",
                variants: [],
            });
            const [nextProducts, nextStats] = await Promise.all([
                getAdminProducts(20),
                getAdminStats(),
            ]);
            setProducts(nextProducts);
            setStats(nextStats);
            setNewProductName("");
            setNewProductDescription("");
            setNewProductPrice("");
            setShowProductForm(false);
            addToast("Product created", "success");
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to create product";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleDeleteProduct = async (productId: string) => {
        const confirmed = window.confirm("Delete this product? This cannot be undone.");
        if (!confirmed) {
            return;
        }
        const busyKey = `product-delete-${productId}`;
        const previousProducts = [...products];
        setActionBusyKey(busyKey);
        setTabActionError(null);
        setProducts((prev) => prev.filter((product) => product.id !== productId));
        try {
            await deleteProduct(productId);
            const nextStats = await getAdminStats();
            setStats(nextStats);
            addToast("Product deleted", "success");
        } catch (err) {
            setProducts(previousProducts);
            const message = err instanceof Error ? err.message : "Failed to delete product";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleCategoryStatus = async (category: AdminCategory, status: string) => {
        const busyKey = `category-status-${category.id}`;
        const previousCategories = [...categories];
        setActionBusyKey(busyKey);
        setTabActionError(null);
        setCategories((prev) => prev.map((item) => item.id === category.id ? { ...item, status } : item));
        try {
            await updateAdminCategory(category.id, { status });
            addToast("Category updated", "success");
        } catch (err) {
            setCategories(previousCategories);
            const message = err instanceof Error ? err.message : "Failed to update category";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleDeleteCategory = async (categoryId: string) => {
        const confirmed = window.confirm("Delete this category? This cannot be undone.");
        if (!confirmed) {
            return;
        }
        const busyKey = `category-delete-${categoryId}`;
        const previousCategories = [...categories];
        setActionBusyKey(busyKey);
        setTabActionError(null);
        setCategories((prev) => prev.filter((category) => category.id !== categoryId));
        try {
            await deleteAdminCategory(categoryId);
            addToast("Category deleted", "success");
        } catch (err) {
            setCategories(previousCategories);
            const message = err instanceof Error ? err.message : "Failed to delete category";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleLoadInventory = async () => {
        if (!selectedVariantId) {
            addToast("Choose a variant first", "warning");
            return;
        }
        setActionBusyKey("inventory-load");
        setTabActionError(null);
        try {
            const row = await getAdminInventory(selectedVariantId);
            setInventory(row);
            setInventoryTotal(String(row.totalQuantity));
            setInventoryAvailable(String(row.availableQuantity));
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to load inventory";
            setTabActionError(message);
            addToast(message, "error");
            setInventory(null);
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleSaveInventory = async () => {
        if (!selectedVariantId) {
            addToast("Choose a variant first", "warning");
            return;
        }
        setActionBusyKey("inventory-save");
        setTabActionError(null);
        try {
            const updated = await updateAdminInventory(selectedVariantId, {
                totalQuantity: Number(inventoryTotal),
                availableQuantity: Number(inventoryAvailable),
            });
            setInventory(updated);
            addToast("Inventory updated", "success");
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to update inventory";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleSupportStatus = async (ticketId: string, status: string) => {
        if (status === "resolved") {
            const confirmed = window.confirm("Mark this support ticket as resolved?");
            if (!confirmed) {
                return;
            }
        }
        const busyKey = `support-${ticketId}-${status}`;
        const previousTickets = [...supportTickets];
        setActionBusyKey(busyKey);
        setTabActionError(null);
        setSupportTickets((prev) => prev.map((ticket) => ticket.id === ticketId ? { ...ticket, status } : ticket));
        try {
            await updateAdminSupportTicket(ticketId, { status, note: `Updated from admin dashboard to ${status}` });
            addToast("Support ticket updated", "success");
        } catch (err) {
            setSupportTickets(previousTickets);
            const message = err instanceof Error ? err.message : "Failed to update support ticket";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleVoiceProcessNow = async () => {
        setActionBusyKey("voice-process");
        setTabActionError(null);
        try {
            await runVoiceRecoveryProcess();
            addToast("Voice recovery run triggered", "success");
            const [calls, jobs, stats] = await Promise.all([
                getVoiceCalls(20),
                getVoiceJobs(20),
                getVoiceStats(),
            ]);
            setVoiceCalls(calls);
            setVoiceJobs(jobs);
            setVoiceStats(stats);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to run voice recovery";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

    const handleToggleVoiceKillSwitch = async () => {
        if (!voiceSettings) return;
        const nextKillSwitch = !(voiceSettings.killSwitch ?? false);
        const confirmed = window.confirm(
            nextKillSwitch
                ? "Enable voice kill switch and pause voice recovery actions?"
                : "Disable voice kill switch and allow voice recovery actions?"
        );
        if (!confirmed) {
            return;
        }
        const previousSettings = voiceSettings;
        setActionBusyKey("voice-kill-switch");
        setTabActionError(null);
        setVoiceSettings({ ...voiceSettings, killSwitch: nextKillSwitch });
        try {
            const updated = await updateVoiceSettings({ killSwitch: nextKillSwitch });
            setVoiceSettings(updated);
            addToast("Voice kill switch updated", "success");
        } catch (err) {
            setVoiceSettings(previousSettings);
            const message = err instanceof Error ? err.message : "Failed to update voice settings";
            setTabActionError(message);
            addToast(message, "error");
        } finally {
            setActionBusyKey(null);
        }
    };

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

                {tabActionError && (
                    <div className="flex items-center gap-3 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-700">
                        <AlertCircle size={18} className="shrink-0" />
                        <span className="text-sm font-medium">{tabActionError}</span>
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

                            {/* Right column items */}
                            <div className="space-y-5">
                                {/* AI Engine Status */}
                                <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-6 space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h2 className="font-bold text-slate-900 flex items-center gap-2">
                                            <Sparkles size={16} className="text-violet-600" /> AI Engine
                                        </h2>
                                        {health?.services?.llm?.enabled ? (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-700 uppercase tracking-widest">Active</span>
                                        ) : (
                                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 uppercase tracking-widest">Offline</span>
                                        )}
                                    </div>
                                    <div className="space-y-2 text-xs">
                                        {(() => {
                                            const circuitState =
                                                health?.services?.llm?.circuitBreakerState ??
                                                health?.services?.llm?.circuit_breaker ??
                                                "";
                                            return (
                                                <>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Provider</span>
                                            <span className="font-medium text-slate-900 capitalize">{health?.services?.llm?.provider || "—"}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Circuit Breaker</span>
                                            <span className={`font-medium ${circuitState === 'closed' ? 'text-emerald-600' : 'text-amber-600'}`}>
                                                {circuitState || "—"}
                                            </span>
                                        </div>
                                                </>
                                            );
                                        })()}
                                    </div>
                                    <div className="pt-2 border-t border-slate-100">
                                        <p className="text-[10px] text-slate-400 text-center">
                                            Configure AI models and agents via .env variables.
                                        </p>
                                    </div>
                                </div>

                                {/* Activity Integrity check */}
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
                            <button
                                onClick={() => {
                                    setShowProductForm((prev) => !prev);
                                    if (!newProductCategory && categories.length > 0) {
                                        setNewProductCategory(categories[0].slug);
                                    }
                                }}
                                className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 text-white text-sm font-semibold rounded-xl hover:bg-violet-700 transition-colors shadow-sm"
                            >
                                <Plus size={16} /> {showProductForm ? "Hide Form" : "Add Product"}
                            </button>
                        </div>

                        {showProductForm && (
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
                                <Input
                                    label="Name"
                                    value={newProductName}
                                    onChange={(e) => setNewProductName(e.target.value)}
                                    placeholder="Trail Runner X"
                                />
                                <Input
                                    label="Description"
                                    value={newProductDescription}
                                    onChange={(e) => setNewProductDescription(e.target.value)}
                                    placeholder="Lightweight all-terrain shoe"
                                />
                                <Input
                                    label="Category Slug"
                                    value={newProductCategory}
                                    onChange={(e) => setNewProductCategory(e.target.value)}
                                    placeholder="running-shoes"
                                />
                                <Input
                                    label="Price (USD)"
                                    type="number"
                                    min="0.01"
                                    step="0.01"
                                    value={newProductPrice}
                                    onChange={(e) => setNewProductPrice(e.target.value)}
                                    placeholder="129.99"
                                />
                                <div className="flex items-end">
                                    <button
                                        className="w-full px-3 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-60 disabled:cursor-not-allowed"
                                        disabled={actionBusyKey === "product-create"}
                                        onClick={handleCreateProduct}
                                    >
                                        {actionBusyKey === "product-create" ? "Creating..." : "Create Product"}
                                    </button>
                                </div>
                            </div>
                        )}

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
                                            <th className="text-left py-3.5 px-4">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {products.map((p) => (
                                            <tr key={p.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 font-medium text-slate-800">{p.name}</td>
                                                <td className="py-4 px-4 text-xs"><StatusBadge status={p.category} /></td>
                                                <td className="py-4 px-4 text-xs text-slate-500">{p.variants?.length ?? 0} variant(s)</td>
                                                <td className="py-4 px-6 text-right font-bold text-slate-700">${p.price.toFixed(2)}</td>
                                                <td className="py-4 px-4">
                                                    <button
                                                        className="px-2 py-1 rounded-lg text-xs bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                        disabled={actionBusyKey === `product-delete-${p.id}`}
                                                        onClick={() => handleDeleteProduct(p.id)}
                                                    >
                                                        {actionBusyKey === `product-delete-${p.id}` ? "Deleting..." : "Delete"}
                                                    </button>
                                                </td>
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

                {activeTab === "support" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">Support Tickets</h1>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : supportTickets.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No support tickets found</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Ticket</th>
                                            <th className="text-left py-3.5 px-4">Category</th>
                                            <th className="text-left py-3.5 px-4">Priority</th>
                                            <th className="text-left py-3.5 px-4">Status</th>
                                            <th className="text-left py-3.5 px-4">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {supportTickets.map((ticket) => (
                                            <tr key={ticket.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6">
                                                    <div className="font-mono text-xs text-slate-500">#{ticket.id.slice(-10).toUpperCase()}</div>
                                                    <div className="text-xs text-slate-700 mt-1 line-clamp-1">{ticket.issue}</div>
                                                </td>
                                                <td className="py-4 px-4 text-xs text-slate-600">{ticket.category}</td>
                                                <td className="py-4 px-4"><StatusBadge status={ticket.priority} /></td>
                                                <td className="py-4 px-4"><StatusBadge status={ticket.status} /></td>
                                                <td className="py-4 px-4">
                                                    <div className="flex gap-2">
                                                        <button
                                                            className="px-2 py-1 rounded-lg text-xs bg-slate-100 hover:bg-slate-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                            disabled={actionBusyKey === `support-${ticket.id}-in_progress` || actionBusyKey === `support-${ticket.id}-resolved`}
                                                            onClick={() => handleSupportStatus(ticket.id, "in_progress")}
                                                        >
                                                            {actionBusyKey === `support-${ticket.id}-in_progress` ? "Updating..." : "In Progress"}
                                                        </button>
                                                        <button
                                                            className="px-2 py-1 rounded-lg text-xs bg-emerald-100 text-emerald-700 hover:bg-emerald-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                            disabled={actionBusyKey === `support-${ticket.id}-in_progress` || actionBusyKey === `support-${ticket.id}-resolved`}
                                                            onClick={() => handleSupportStatus(ticket.id, "resolved")}
                                                        >
                                                            {actionBusyKey === `support-${ticket.id}-resolved` ? "Updating..." : "Resolve"}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === "voice" && (
                    <div className="space-y-6 animate-fade-in">
                        <div className="flex items-center justify-between">
                            <h1 className="text-2xl font-bold text-slate-900">Voice Recovery</h1>
                            <div className="flex gap-2">
                                <button
                                    onClick={handleToggleVoiceKillSwitch}
                                    disabled={actionBusyKey === "voice-kill-switch"}
                                    className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                >
                                    {actionBusyKey === "voice-kill-switch" ? "Updating..." : voiceSettings?.killSwitch ? "Disable Kill Switch" : "Enable Kill Switch"}
                                </button>
                                <button
                                    onClick={handleVoiceProcessNow}
                                    disabled={actionBusyKey === "voice-process"}
                                    className="px-3 py-2 rounded-xl text-xs font-semibold bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-60 disabled:cursor-not-allowed"
                                >
                                    {actionBusyKey === "voice-process" ? "Processing..." : "Process Now"}
                                </button>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4">
                                <div className="text-xs text-slate-500">Voice Enabled</div>
                                <div className="text-lg font-bold mt-1">{String(voiceSettings?.enabled ?? false)}</div>
                            </div>
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4">
                                <div className="text-xs text-slate-500">Kill Switch</div>
                                <div className="text-lg font-bold mt-1">{String(voiceSettings?.killSwitch ?? false)}</div>
                            </div>
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4">
                                <div className="text-xs text-slate-500">Stats Snapshot</div>
                                <div className="text-lg font-bold mt-1">{voiceStats ? "Available" : "—"}</div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                                <div className="px-4 py-3 border-b border-slate-100 font-semibold text-sm">Recent Voice Jobs</div>
                                <div className="max-h-80 overflow-auto">
                                    {voiceJobs.length === 0 ? (
                                        <div className="p-4 text-sm text-slate-500">No jobs found.</div>
                                    ) : voiceJobs.map((job) => (
                                        <div key={job.id} className="px-4 py-3 border-b border-slate-50 last:border-0 text-xs flex items-center justify-between">
                                            <span className="font-mono text-slate-500">{job.id}</span>
                                            <StatusBadge status={job.status} />
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                                <div className="px-4 py-3 border-b border-slate-100 font-semibold text-sm">Recent Voice Calls</div>
                                <div className="max-h-80 overflow-auto">
                                    {voiceCalls.length === 0 ? (
                                        <div className="p-4 text-sm text-slate-500">No calls found.</div>
                                    ) : voiceCalls.map((call) => (
                                        <div key={call.id} className="px-4 py-3 border-b border-slate-50 last:border-0 text-xs flex items-center justify-between">
                                            <span className="font-mono text-slate-500">{call.id}</span>
                                            <StatusBadge status={call.status} />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === "categories" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">Categories</h1>
                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                            <Input label="Name" value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} placeholder="Running Shoes" />
                            <Input label="Slug" value={newCategorySlug} onChange={(e) => setNewCategorySlug(e.target.value)} placeholder="running-shoes" />
                            <Input label="Description" value={newCategoryDescription} onChange={(e) => setNewCategoryDescription(e.target.value)} placeholder="Category description" />
                            <div className="flex items-end">
                                <button
                                    className="w-full px-3 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-60 disabled:cursor-not-allowed"
                                    disabled={actionBusyKey === "category-create"}
                                    onClick={handleCreateCategory}
                                >
                                    {actionBusyKey === "category-create" ? "Creating..." : "Create Category"}
                                </button>
                            </div>
                        </div>

                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
                            {loading ? (
                                <div className="p-6 space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
                            ) : categories.length === 0 ? (
                                <div className="p-16 text-center text-slate-400">No categories found</div>
                            ) : (
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr className="text-xs uppercase tracking-wider text-slate-400">
                                            <th className="text-left py-3.5 px-6">Name</th>
                                            <th className="text-left py-3.5 px-4">Slug</th>
                                            <th className="text-left py-3.5 px-4">Status</th>
                                            <th className="text-left py-3.5 px-4">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {categories.map((category) => (
                                            <tr key={category.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                                                <td className="py-4 px-6 font-medium text-slate-800">{category.name}</td>
                                                <td className="py-4 px-4 text-xs text-slate-600">{category.slug}</td>
                                                <td className="py-4 px-4"><StatusBadge status={category.status} /></td>
                                                <td className="py-4 px-4">
                                                    <div className="flex gap-2">
                                                        {category.status === "active" ? (
                                                            <button
                                                                className="px-2 py-1 rounded-lg text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                                disabled={actionBusyKey === `category-status-${category.id}` || actionBusyKey === `category-delete-${category.id}`}
                                                                onClick={() => handleCategoryStatus(category, "archived")}
                                                            >
                                                                {actionBusyKey === `category-status-${category.id}` ? "Updating..." : "Archive"}
                                                            </button>
                                                        ) : (
                                                            <button
                                                                className="px-2 py-1 rounded-lg text-xs bg-emerald-100 text-emerald-700 hover:bg-emerald-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                                disabled={actionBusyKey === `category-status-${category.id}` || actionBusyKey === `category-delete-${category.id}`}
                                                                onClick={() => handleCategoryStatus(category, "active")}
                                                            >
                                                                {actionBusyKey === `category-status-${category.id}` ? "Updating..." : "Activate"}
                                                            </button>
                                                        )}
                                                        <button
                                                            className="px-2 py-1 rounded-lg text-xs bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                                            disabled={actionBusyKey === `category-status-${category.id}` || actionBusyKey === `category-delete-${category.id}`}
                                                            onClick={() => handleDeleteCategory(category.id)}
                                                        >
                                                            {actionBusyKey === `category-delete-${category.id}` ? "Deleting..." : "Delete"}
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === "inventory" && (
                    <div className="space-y-6 animate-fade-in">
                        <h1 className="text-2xl font-bold text-slate-900">Inventory Control</h1>

                        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                            <div className="space-y-1.5">
                                <label className="text-sm font-medium text-slate-700 ml-1">Product</label>
                                <select
                                    className="h-11 w-full rounded-xl border border-line bg-surface-50 px-4 text-sm"
                                    aria-label="Product"
                                    value={selectedProductId}
                                    onChange={(e) => {
                                        setSelectedProductId(e.target.value);
                                        setSelectedVariantId("");
                                        setInventory(null);
                                    }}
                                >
                                    <option value="">Select product</option>
                                    {products.map((product) => (
                                        <option key={product.id} value={product.id}>{product.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="space-y-1.5">
                                <label className="text-sm font-medium text-slate-700 ml-1">Variant</label>
                                <select
                                    className="h-11 w-full rounded-xl border border-line bg-surface-50 px-4 text-sm"
                                    aria-label="Variant"
                                    value={selectedVariantId}
                                    onChange={(e) => {
                                        setSelectedVariantId(e.target.value);
                                        setInventory(null);
                                    }}
                                    disabled={!selectedProduct}
                                >
                                    <option value="">Select variant</option>
                                    {(selectedProduct?.variants ?? []).map((variant) => (
                                        <option key={variant.id} value={variant.id}>{variant.id}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex items-end">
                                <button
                                    className="w-full px-3 py-2.5 rounded-xl bg-slate-100 text-sm font-semibold hover:bg-slate-200 disabled:opacity-60 disabled:cursor-not-allowed"
                                    disabled={actionBusyKey === "inventory-load"}
                                    onClick={handleLoadInventory}
                                >
                                    {actionBusyKey === "inventory-load" ? "Loading..." : "Load Inventory"}
                                </button>
                            </div>
                        </div>

                        {inventory && (
                            <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                                <Input label="Total Quantity" type="number" min={0} value={inventoryTotal} onChange={(e) => setInventoryTotal(e.target.value)} />
                                <Input label="Available Quantity" type="number" min={0} value={inventoryAvailable} onChange={(e) => setInventoryAvailable(e.target.value)} />
                                <div className="space-y-1.5">
                                    <label className="text-sm font-medium text-slate-700 ml-1">Reserved Quantity</label>
                                    <div className="h-11 rounded-xl border border-line bg-surface-50 px-4 flex items-center text-sm text-slate-700">
                                        {inventory.reservedQuantity}
                                    </div>
                                </div>
                                <div className="flex items-end">
                                    <button
                                        className="w-full px-3 py-2.5 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-60 disabled:cursor-not-allowed"
                                        disabled={actionBusyKey === "inventory-save"}
                                        onClick={handleSaveInventory}
                                    >
                                        {actionBusyKey === "inventory-save" ? "Saving..." : "Save Inventory"}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                )}

            </main>
        </div>
    );
};

export { AdminDashboard };

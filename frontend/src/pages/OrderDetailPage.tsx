import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
    ChevronLeft,
    Package,
    Truck,
    CheckCircle2,
    Clock,
    CreditCard,
    MapPin,
    Calendar,
    ArrowRight,
    AlertCircle,
    Copy,
    ExternalLink
} from "lucide-react";
import { fetchOrderById, cancelOrder, refundOrder } from "../api";
import type { OrderDetail } from "../types";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../context/ToastContext";
import { cn } from "../utils/cn";

const OrderDetailPage: React.FC = () => {
    const { orderId } = useParams<{ orderId: string }>();
    const navigate = useNavigate();
    const { addToast } = useToast();
    const [order, setOrder] = useState<OrderDetail | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isActionLoading, setIsActionLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadOrder = async () => {
        if (!orderId) return;
        try {
            setIsLoading(true);
            const data = await fetchOrderById(orderId);
            setOrder(data);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Could not find this order.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        loadOrder();
    }, [orderId]);

    const handleCancel = async () => {
        if (!order || !window.confirm("Are you sure you want to cancel this order?")) return;
        setIsActionLoading(true);
        try {
            await cancelOrder(order.id, "Customer requested cancellation via UI");
            addToast("Order successfully cancelled", "info");
            await loadOrder();
        } catch (err: unknown) {
            addToast(err instanceof Error ? err.message : "Failed to cancel order", "error");
        } finally {
            setIsActionLoading(false);
        }
    };

    const handleRefund = async () => {
        if (!order || !window.confirm("Are you sure you want to request a refund for this order?")) return;
        setIsActionLoading(true);
        try {
            await refundOrder(order.id, "Customer requested refund via UI");
            addToast("Refund requested successfully", "success");
            await loadOrder();
        } catch (err: unknown) {
            addToast(err instanceof Error ? err.message : "Failed to request refund", "error");
        } finally {
            setIsActionLoading(false);
        }
    };

    const getStatusStyles = (status: string) => {
        switch (status.toLowerCase()) {
            case "confirmed": return { icon: CheckCircle2, bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-100", label: "Confirmed" };
            case "processing": return { icon: Clock, bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-100", label: "Processing" };
            case "shipped": return { icon: Truck, bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-100", label: "Shipped" };
            case "delivered": return { icon: CheckCircle2, bg: "bg-emerald-100", text: "text-emerald-800", border: "border-emerald-200", label: "Delivered" };
            case "cancelled": return { icon: AlertCircle, bg: "bg-red-50", text: "text-red-700", border: "border-red-100", label: "Cancelled" };
            default: return { icon: Package, bg: "bg-slate-50", text: "text-slate-700", border: "border-slate-100", label: status };
        }
    };

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto py-20 flex flex-col items-center justify-center space-y-6">
                <div className="w-12 h-12 border-4 border-brand border-t-transparent rounded-full animate-spin" />
                <p className="text-slate-500 font-medium animate-pulse">Retrieving order details...</p>
            </div>
        );
    }

    if (error || !order) {
        return (
            <div className="max-w-2xl mx-auto py-20 text-center space-y-6">
                <div className="w-20 h-20 bg-red-50 text-red-500 rounded-3xl flex items-center justify-center mx-auto">
                    <AlertCircle size={40} />
                </div>
                <div className="space-y-2">
                    <h1 className="text-2xl font-bold">Order Not Found</h1>
                    <p className="text-slate-500">{error || "The order you're looking for doesn't exist or you don't have access to it."}</p>
                </div>
                <Button onClick={() => navigate("/account")} variant="outline" className="rounded-2xl">
                    Back to Account
                </Button>
            </div>
        );
    }

    const { icon: StatusIcon, bg, text, border, label } = getStatusStyles(order.status);

    return (
        <div className="max-w-5xl mx-auto space-y-8 pb-20 animate-fade-in">
            {/* Header Navigation */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <button
                    onClick={() => navigate("/account")}
                    className="group flex items-center gap-2 text-slate-500 hover:text-brand transition-colors font-medium px-2 py-1 -ml-2 rounded-lg"
                >
                    <ChevronLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
                    Back to Account
                </button>
                <div className="flex flex-wrap items-center gap-3">
                    {order.status.toLowerCase() !== "cancelled" && order.status.toLowerCase() !== "delivered" && order.status.toLowerCase() !== "refund_requested" && order.status.toLowerCase() !== "refunded" && (
                        <Button
                            variant="danger"
                            size="sm"
                            className="rounded-xl font-bold h-10"
                            onClick={handleCancel}
                            disabled={isActionLoading}
                        >
                            <AlertCircle size={16} className="mr-2" /> Cancel Order
                        </Button>
                    )}
                    {order.status.toLowerCase() === "delivered" && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="rounded-xl font-bold h-10 text-slate-600 hover:text-red-600 hover:bg-red-50 border-slate-200 hover:border-red-200"
                            onClick={handleRefund}
                            disabled={isActionLoading}
                        >
                            <AlertCircle size={16} className="mr-2" /> Request Refund
                        </Button>
                    )}
                    <Button variant="outline" size="sm" className="rounded-xl gap-2 font-bold h-10">
                        <Package size={16} /> Invoice PDF
                    </Button>
                </div>
            </div>

            {/* Simple Summary Bar */}
            <div className={cn("p-6 rounded-[32px] border flex flex-col md:flex-row items-center justify-between gap-6", bg, border)}>
                <div className="flex items-center gap-4">
                    <div className={cn("w-14 h-14 rounded-2xl flex items-center justify-center bg-white shadow-sm", text)}>
                        <StatusIcon size={28} />
                    </div>
                    <div>
                        <div className="text-xs font-bold uppercase tracking-wider opacity-60">Status</div>
                        <div className={cn("text-xl font-black", text)}>{label}</div>
                    </div>
                </div>

                <div className="hidden md:block w-px h-10 bg-slate-200/50" />

                <div className="text-center md:text-left">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500/60">Order ID</div>
                    <div className="text-lg font-mono font-bold text-slate-900 flex items-center gap-2">
                        #{order.id.slice(0, 12).toUpperCase()}
                        <button
                            className="text-slate-300 hover:text-slate-500"
                            aria-label="Copy order id"
                            title="Copy order id"
                        >
                            <Copy size={14} />
                        </button>
                    </div>
                </div>

                <div className="hidden md:block w-px h-10 bg-slate-200/50" />

                <div className="text-center md:text-left">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500/60">Estimated Delivery</div>
                    <div className="text-lg font-bold text-slate-900 flex items-center gap-2">
                        <Calendar size={18} className="text-brand" />
                        {order.estimatedDelivery ? new Date(order.estimatedDelivery).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' }) : 'TBD'}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content: Items */}
                <div className="lg:col-span-2 space-y-8">
                    <div className="premium-card">
                        <h3 className="text-xl font-bold mb-6 flex items-center gap-3">
                            Items ({order.itemCount})
                        </h3>
                        <div className="divide-y divide-line">
                            {order.items.map((item, idx) => (
                                <div key={idx} className="py-6 first:pt-0 last:pb-0 flex items-center gap-6">
                                    <div className="w-24 h-24 rounded-2xl bg-surface-50 border border-line overflow-hidden flex-shrink-0 relative group">
                                        <img src={item.image} alt={item.name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h4 className="font-bold text-slate-900 hover:text-brand cursor-pointer truncate">{item.name}</h4>
                                        <p className="text-sm text-slate-500 mt-1">Quantity: {item.quantity}</p>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-black text-slate-900 text-lg">${(item.price * item.quantity).toFixed(2)}</div>
                                        <div className="text-xs text-slate-400 font-medium">${item.price.toFixed(2)} each</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Timeline */}
                    <div className="premium-card">
                        <h3 className="text-xl font-bold mb-8">Order Timeline</h3>
                        <div className="space-y-8">
                            {order.timeline.map((event, idx) => (
                                <div key={idx} className="flex gap-4 relative">
                                    {idx !== order.timeline.length - 1 && (
                                        <div className="absolute left-3.5 top-8 bottom-[-24px] w-0.5 bg-line" />
                                    )}
                                    <div className={cn(
                                        "w-7 h-7 rounded-full flex items-center justify-center z-10",
                                        idx === 0 ? "bg-brand text-white shadow-lg shadow-brand/20" : "bg-line text-slate-400"
                                    )}>
                                        <div className="w-2 h-2 rounded-full bg-current" />
                                    </div>
                                    <div className="flex-1 pb-2">
                                        <div className="flex items-center justify-between">
                                            <h4 className={cn("font-bold capitalize", idx === 0 ? "text-slate-900" : "text-slate-500")}>
                                                {event.status.replace(/_/g, ' ')}
                                            </h4>
                                            <span className="text-xs font-medium text-slate-400">
                                                {new Date(event.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                        {event.note && <p className="text-sm text-slate-500 mt-1">{event.note}</p>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Sidebar: Totals, Shipping, Payment */}
                <div className="space-y-8">
                    {/* Order Summary */}
                    <div className="premium-card bg-surface-900 text-white">
                        <h3 className="text-lg font-bold mb-6">Payment Summary</h3>
                        <div className="space-y-4 text-sm">
                            <div className="flex justify-between items-center opacity-70">
                                <span>Subtotal</span>
                                <span className="font-medium">${order.subtotal.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between items-center opacity-70">
                                <span>Shipping Fee</span>
                                <span className="font-medium">${order.shipping.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between items-center opacity-70">
                                <span>Sales Tax</span>
                                <span className="font-medium">${order.tax.toFixed(2)}</span>
                            </div>
                            {order.discount > 0 && (
                                <div className="flex justify-between items-center text-emerald-400">
                                    <span>Discount</span>
                                    <span className="font-medium">-${order.discount.toFixed(2)}</span>
                                </div>
                            )}
                            <div className="pt-4 border-t border-white/10 flex justify-between items-center mt-4">
                                <span className="text-lg font-bold">Total Amount</span>
                                <span className="text-2xl font-black text-brand-light">${order.total.toFixed(2)}</span>
                            </div>
                        </div>

                        <div className="mt-8 p-4 rounded-2xl bg-white/5 border border-white/10 flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                                <CreditCard size={20} className="text-brand-light" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-[10px] uppercase tracking-widest font-bold opacity-50">Charged To</div>
                                <div className="text-sm font-bold capitalize truncate">{order.payment.method} Method</div>
                            </div>
                            <Badge variant="outline" className="text-[10px] border-white/20 text-white">Paid</Badge>
                        </div>
                    </div>

                    {/* Delivery Details */}
                    <div className="premium-card">
                        <h3 className="text-lg font-bold mb-6 flex items-center gap-3">
                            <MapPin size={20} className="text-slate-400" />
                            Delivery Address
                        </h3>
                        <div className="space-y-1">
                            <div className="font-bold text-slate-900">{order.shippingAddress.name}</div>
                            <div className="text-slate-500 text-sm">{order.shippingAddress.line1}</div>
                            <div className="text-slate-500 text-sm">
                                {order.shippingAddress.city}, {order.shippingAddress.state} {order.shippingAddress.postalCode}
                            </div>
                            <div className="text-slate-500 text-sm">{order.shippingAddress.country}</div>
                        </div>

                        {order.tracking.trackingNumber && (
                            <div className="mt-8 pt-8 border-t border-line space-y-4">
                                <div className="flex items-center justify-between">
                                    <div className="text-sm font-bold text-slate-900">Track Shipment</div>
                                    <Badge variant="secondary" className="bg-blue-50 text-blue-700 text-[10px]">{order.tracking.status}</Badge>
                                </div>
                                <div className="flex items-center justify-between bg-surface-50 p-4 rounded-2xl border border-line">
                                    <div className="text-xs">
                                        <div className="text-slate-400 font-medium">Carrier</div>
                                        <div className="font-bold text-slate-900">{order.tracking.carrier || 'Standard Proxy'}</div>
                                    </div>
                                    <ArrowRight size={14} className="text-slate-300" />
                                    <div className="text-right text-xs">
                                        <div className="text-slate-400 font-medium">Number</div>
                                        <div className="font-mono font-bold text-slate-900">{order.tracking.trackingNumber}</div>
                                    </div>
                                </div>
                                <Button variant="ghost" className="w-full rounded-xl text-brand font-bold gap-2">
                                    Track on Carrier <ExternalLink size={14} />
                                </Button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default OrderDetailPage;

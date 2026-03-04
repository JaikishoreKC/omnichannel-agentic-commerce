import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShoppingBag, Trash2, Plus, Minus, ArrowRight, CreditCard, Truck, ShieldCheck, X } from "lucide-react";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { checkout, applyDiscount } from "../api";

interface CheckoutFormData {
    name: string;
    line1: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
}

const CartPage: React.FC = () => {
    const { cart, refreshCart, updateItemQuantity, removeItem, isLoading: isCartLoading } = useCart();
    const { isAuthenticated } = useAuth();
    const { addToast } = useToast();
    const navigate = useNavigate();
    const [isCheckingOut, setIsCheckingOut] = useState(false);
    const [showCheckoutModal, setShowCheckoutModal] = useState(false);
    const [checkoutError, setCheckoutError] = useState<string | null>(null);
    const [discountCode, setDiscountCode] = useState("");
    const [isApplyingDiscount, setIsApplyingDiscount] = useState(false);
    const [form, setForm] = useState<CheckoutFormData>({
        name: "", line1: "", city: "", state: "", postalCode: "", country: "US"
    });

    const handleApplyDiscount = async () => {
        if (!discountCode.trim()) return;
        setIsApplyingDiscount(true);
        try {
            await applyDiscount(discountCode.trim());
            await refreshCart();
            addToast("Discount applied successfully!", "success");
            setDiscountCode("");
        } catch (err: any) {
            addToast(err.message || "Invalid or expired discount code", "error");
        } finally {
            setIsApplyingDiscount(false);
        }
    };

    const handleCheckout = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!isAuthenticated) {
            navigate("/login?redirect=/cart");
            return;
        }
        setIsCheckingOut(true);
        setCheckoutError(null);
        try {
            await checkout({
                shippingAddress: form,
                paymentMethod: { type: "card", token: "tok_visa" } // Simulated payment
            });
            await refreshCart();
            setShowCheckoutModal(false);
            addToast("Order placed successfully! Redirecting...", "success");
            navigate("/account");
        } catch (err) {
            setCheckoutError(err instanceof Error ? err.message : "Checkout failed. Please try again.");
            addToast("Checkout failed. Please try again.", "error");
        } finally {
            setIsCheckingOut(false);
        }
    };

    const handleCheckoutClick = () => {
        if (!isAuthenticated) {
            navigate("/login?redirect=/cart");
            return;
        }
        setShowCheckoutModal(true);
    };

    if (isCartLoading && !cart) {
        return (
            <div className="py-24 text-center space-y-4">
                <div className="animate-spin inline-block w-8 h-8 border-4 border-brand border-t-transparent rounded-full" />
                <p className="text-slate-500 font-medium">Crunching your cart data...</p>
            </div>
        );
    }

    if (!cart || cart.items.length === 0) {
        return (
            <div className="py-24 flex flex-col items-center justify-center text-center space-y-6">
                <div className="w-24 h-24 rounded-[32px] bg-surface-100 flex items-center justify-center text-slate-300">
                    <ShoppingBag size={48} />
                </div>
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold">Your bag is empty</h1>
                    <p className="text-slate-500 max-w-xs">Looks like you haven't added anything to your bag yet.</p>
                </div>
                <Link to="/products">
                    <Button size="lg" className="rounded-2xl px-8">
                        Start Shopping
                    </Button>
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-12 animate-fade-in">
            <h1 className="text-4xl font-bold">Shopping <span className="text-brand">Bag</span></h1>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 items-start">
                {/* Cart Items */}
                <div className="lg:col-span-2 space-y-6" data-testid="cart-list">
                    {cart.items.map((item) => (
                        <div key={item.itemId} className="premium-card flex flex-col sm:flex-row items-center gap-6 p-4">
                            <div className="w-24 h-24 rounded-2xl bg-surface-50 shrink-0 p-4 border border-line flex items-center justify-center">
                                <img src={item.image} alt={item.name} className="w-full h-full object-contain" />
                            </div>

                            <div className="flex-1 space-y-1 text-center sm:text-left">
                                <h4 className="font-bold text-lg">{item.name}</h4>
                                <p className="text-sm text-slate-500">Variant: {item.variantId.split("_").pop()}</p>
                                <div className="text-brand font-bold mt-2">${item.price.toFixed(2)}</div>
                            </div>

                            <div className="flex items-center gap-4 bg-surface-50 rounded-xl border border-line p-1">
                                <button
                                    className="p-2 hover:text-brand transition-colors"
                                    onClick={() => updateItemQuantity(item.itemId, item.quantity - 1)}
                                >
                                    <Minus size={16} />
                                </button>
                                <span className="w-8 text-center font-bold">{item.quantity}</span>
                                <button
                                    className="p-2 hover:text-brand transition-colors"
                                    onClick={() => updateItemQuantity(item.itemId, item.quantity + 1)}
                                >
                                    <Plus size={16} />
                                </button>
                            </div>

                            <button
                                className="p-2 text-slate-300 hover:text-red-500 transition-colors"
                                onClick={() => removeItem(item.itemId)}
                            >
                                <Trash2 size={20} />
                            </button>
                        </div>
                    ))}
                </div>

                {/* Summary */}
                <div className="space-y-6">
                    <div className="premium-card bg-ink text-white">
                        <h3 className="text-xl font-bold mb-6">Order Summary</h3>

                        <div className="space-y-4 text-sm opacity-80">
                            <div className="flex justify-between">
                                <span>Subtotal</span>
                                <span>${cart.subtotal.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Shipping</span>
                                <span>{cart.shipping === 0 ? "FREE" : `$${cart.shipping.toFixed(2)}`}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Tax</span>
                                <span>${cart.tax.toFixed(2)}</span>
                            </div>
                            {cart.discount > 0 && (
                                <div className="flex justify-between text-emerald-400">
                                    <span>Discount</span>
                                    <span>-${cart.discount.toFixed(2)}</span>
                                </div>
                            )}
                        </div>

                        <div className="h-px bg-white/10 my-6" />

                        <div className="flex justify-between text-xl font-bold mb-8">
                            <span>Total</span>
                            <span className="text-brand-light">${cart.total.toFixed(2)}</span>
                        </div>

                        <Button
                            className="w-full h-14 rounded-2xl bg-brand-light hover:bg-white hover:text-ink shadow-lg gap-2"
                            onClick={handleCheckoutClick}
                            data-testid="checkout-button"
                        >
                            Checkout Now <ArrowRight size={20} />
                        </Button>

                        <div className="mt-6 space-y-4">
                            <div className="flex items-center gap-3 text-xs opacity-60">
                                <ShieldCheck size={14} /> Secure Checkout Guarantee
                            </div>
                            <div className="flex items-center gap-3 text-xs opacity-60">
                                <CreditCard size={14} /> All major cards accepted
                            </div>
                        </div>
                    </div>

                    <div className="premium-card bg-surface-50">
                        <h4 className="font-bold text-sm mb-4">Promo Code</h4>
                        <div className="flex gap-2 text-sm text-slate-500">
                            <Input
                                placeholder="Enter code (e.g. SAVE20)"
                                value={discountCode}
                                onChange={(e) => setDiscountCode(e.target.value)}
                                className="flex-1"
                                disabled={isApplyingDiscount}
                                onKeyDown={(e) => e.key === "Enter" && handleApplyDiscount()}
                            />
                            <Button
                                onClick={handleApplyDiscount}
                                disabled={isApplyingDiscount || !discountCode.trim()}
                                className="whitespace-nowrap px-6 rounded-xl"
                            >
                                Apply
                            </Button>
                        </div>
                    </div>

                    <div className="premium-card bg-surface-50 border-dashed">
                        <h4 className="font-bold text-sm mb-4">Estimated Delivery</h4>
                        <div className="flex items-center gap-3 text-sm text-slate-500">
                            <Truck size={20} /> Arriving in 2-3 business days
                        </div>
                    </div>
                </div>
            </div>

            {/* Checkout Modal */}
            {showCheckoutModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
                    <div className="bg-white rounded-[32px] shadow-2xl w-full max-w-lg p-8 space-y-6 relative">
                        <button
                            onClick={() => setShowCheckoutModal(false)}
                            className="absolute top-6 right-6 text-slate-400 hover:text-slate-700 transition-colors"
                        >
                            <X size={20} />
                        </button>
                        <div>
                            <h2 className="text-2xl font-bold">Shipping Details</h2>
                            <p className="text-slate-500 text-sm mt-1">Enter your delivery address to complete the order.</p>
                        </div>

                        {checkoutError && (
                            <div className="p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm font-medium">
                                {checkoutError}
                            </div>
                        )}

                        <form onSubmit={handleCheckout} className="space-y-4">
                            <Input
                                label="Full Name"
                                placeholder="Jane Doe"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                required
                            />
                            <Input
                                label="Street Address"
                                placeholder="123 Commerce Ave"
                                value={form.line1}
                                onChange={(e) => setForm({ ...form, line1: e.target.value })}
                                required
                            />
                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    label="City"
                                    placeholder="New York"
                                    value={form.city}
                                    onChange={(e) => setForm({ ...form, city: e.target.value })}
                                    required
                                />
                                <Input
                                    label="State"
                                    placeholder="NY"
                                    value={form.state}
                                    onChange={(e) => setForm({ ...form, state: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    label="Postal Code"
                                    placeholder="10001"
                                    value={form.postalCode}
                                    onChange={(e) => setForm({ ...form, postalCode: e.target.value })}
                                    required
                                />
                                <Input
                                    label="Country"
                                    placeholder="US"
                                    value={form.country}
                                    onChange={(e) => setForm({ ...form, country: e.target.value })}
                                    required
                                />
                            </div>

                            <div className="p-4 rounded-2xl bg-surface-50 border border-line flex items-center justify-between mt-2">
                                <div className="flex items-center gap-3 text-sm font-medium">
                                    <CreditCard size={18} className="text-slate-400" />
                                    <span>Simulated Payment</span>
                                </div>
                                <Badge variant="secondary">Demo Mode</Badge>
                            </div>

                            <Button
                                type="submit"
                                className="w-full h-13 rounded-2xl gap-2 mt-2"
                                isLoading={isCheckingOut}
                                data-testid="confirm-checkout-button"
                            >
                                Place Order <ArrowRight size={18} />
                            </Button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export { CartPage };

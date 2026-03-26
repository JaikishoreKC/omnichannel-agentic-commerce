import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { currentSessionId, fetchCart as apiFetchCart, addToCart as apiAddToCart, updateCartItem as apiUpdateCartItem, removeFromCart as apiRemoveFromCart } from "../api";
import { ensureSession } from "../api/sessions";
import { useSession } from "./SessionContext";
import { useAuth } from "./AuthContext";
import { useToast } from "./ToastContext";
import type { Cart } from "../types";

interface CartContextType {
    cart: Cart | null;
    isLoading: boolean;
    addItem: (productId: string, variantId: string, quantity: number) => Promise<void>;
    updateItemQuantity: (itemId: string, quantity: number) => Promise<void>;
    removeItem: (itemId: string) => Promise<void>;
    refreshCart: () => Promise<void>;

}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { sessionId } = useSession();
    const { user } = useAuth();
    const [cart, setCart] = useState<Cart | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const { addToast } = useToast();
    const refreshDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const ensureActiveSession = useCallback(async (): Promise<void> => {
        if (sessionId) {
            return;
        }
        await ensureSession();
    }, [sessionId]);

    const refreshCart = useCallback(async () => {
        const activeSessionId = sessionId ?? currentSessionId();
        if (!activeSessionId) return;
        try {
            setIsLoading(true);
            const data = await apiFetchCart();
            setCart(data);
        } catch {
            setCart(null);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        refreshCart();
    }, [sessionId, user, refreshCart]);

    useEffect(() => {
        const handleRefresh = () => {
            if (refreshDebounceRef.current) {
                clearTimeout(refreshDebounceRef.current);
            }
            refreshDebounceRef.current = setTimeout(() => {
                void refreshCart();
            }, 120);
        };
        window.addEventListener("cart:refresh", handleRefresh);
        return () => {
            window.removeEventListener("cart:refresh", handleRefresh);
            if (refreshDebounceRef.current) {
                clearTimeout(refreshDebounceRef.current);
                refreshDebounceRef.current = null;
            }
        };
    }, [refreshCart]);

    const recalculateCartFromItems = useCallback((current: Cart, nextItems: Cart["items"]): Cart => {
        const subtotal = Number(
            nextItems.reduce((sum, item) => sum + item.price * item.quantity, 0).toFixed(2),
        );
        const prevSubtotal = Number(current.subtotal || 0);
        const prevDiscount = Number(current.discount || 0);
        const prevTax = Number(current.tax || 0);
        const prevTaxable = Math.max(0, prevSubtotal - prevDiscount);
        const inferredTaxRate = prevTaxable > 0 ? prevTax / prevTaxable : 0;

        const discount = Number(Math.min(current.discount || 0, subtotal).toFixed(2));
        const taxableBase = Math.max(0, subtotal - discount);
        const tax = Number((taxableBase * inferredTaxRate).toFixed(2));
        const shipping = nextItems.length > 0 ? Number(current.shipping || 0) : 0;
        const total = Number((taxableBase + tax + shipping).toFixed(2));
        const itemCount = nextItems.reduce((sum, item) => sum + item.quantity, 0);

        return {
            ...current,
            items: nextItems,
            subtotal,
            discount,
            tax,
            shipping,
            total,
            itemCount,
        };
    }, []);

    const applyLocalQuantityUpdate = useCallback((current: Cart, itemId: string, quantity: number): Cart => {
        const nextItems = current.items
            .map((item) => (item.itemId === itemId ? { ...item, quantity } : item))
            .filter((item) => item.quantity > 0);
        return recalculateCartFromItems(current, nextItems);
    }, [recalculateCartFromItems]);

    const applyLocalRemove = useCallback((current: Cart, itemId: string): Cart => {
        const nextItems = current.items.filter((item) => item.itemId !== itemId);
        return recalculateCartFromItems(current, nextItems);
    }, [recalculateCartFromItems]);

    const applyLocalAdd = useCallback((current: Cart, productId: string, variantId: string, quantity: number): Cart => {
        const existing = current.items.find((item) => item.productId === productId && item.variantId === variantId);
        if (existing) {
            const nextQuantity = existing.quantity + quantity;
            return applyLocalQuantityUpdate(current, existing.itemId, nextQuantity);
        }

        const provisionalItemId = `pending-${productId}-${variantId}`;
        const nextItems: Cart["items"] = [
            ...current.items,
            {
                itemId: provisionalItemId,
                productId,
                variantId,
                name: "Item",
                price: 0,
                quantity,
                image: "",
            },
        ];
        return recalculateCartFromItems(current, nextItems);
    }, [applyLocalQuantityUpdate, recalculateCartFromItems]);

    const addItem = async (productId: string, variantId: string, quantity: number) => {
        try {
            await ensureActiveSession();
            await apiAddToCart({ productId, variantId, quantity });
            setCart((current) => {
                if (!current) {
                    return {
                        id: "pending",
                        userId: user?.id ?? null,
                        sessionId: sessionId ?? currentSessionId() ?? "pending",
                        items: [
                            {
                                itemId: `pending-${productId}-${variantId}`,
                                productId,
                                variantId,
                                name: "Item",
                                price: 0,
                                quantity,
                                image: "",
                            },
                        ],
                        subtotal: 0,
                        tax: 0,
                        shipping: 0,
                        discount: 0,
                        total: 0,
                        itemCount: quantity,
                        currency: "USD",
                    };
                }
                return applyLocalAdd(current, productId, variantId, quantity);
            });
            setTimeout(() => {
                void refreshCart();
            }, 300);
            addToast("Added to cart", "success");
        } catch (err) {
            addToast("Failed to add to cart", "error");
            throw err;
        }
    };

    const updateItemQuantity = async (itemId: string, quantity: number) => {
        const previousCart = cart;
        try {
            await ensureActiveSession();
            if (previousCart) {
                setCart(quantity < 1 ? applyLocalRemove(previousCart, itemId) : applyLocalQuantityUpdate(previousCart, itemId, quantity));
            }
            if (quantity < 1) {
                await apiRemoveFromCart(itemId);
                addToast("Item removed from cart", "info");
            } else {
                await apiUpdateCartItem(itemId, quantity);
            }
            void refreshCart();
        } catch (err) {
            if (previousCart) {
                setCart(previousCart);
            }
            addToast("Failed to update cart", "error");
            throw err;
        }
    };

    const removeItem = async (itemId: string) => {
        const previousCart = cart;
        try {
            await ensureActiveSession();
            if (previousCart) {
                setCart(applyLocalRemove(previousCart, itemId));
            }
            await apiRemoveFromCart(itemId);
            void refreshCart();
            addToast("Item removed from cart", "info");
        } catch (err) {
            if (previousCart) {
                setCart(previousCart);
            }
            addToast("Failed to remove item", "error");
            throw err;
        }
    };

    return (
        <CartContext.Provider value={{ cart, isLoading, addItem, updateItemQuantity, removeItem, refreshCart }}>
            {children}
        </CartContext.Provider>
    );
};

export const useCart = () => {
    const context = useContext(CartContext);
    if (context === undefined) {
        throw new Error("useCart must be used within a CartProvider");
    }
    return context;
};

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { fetchCart as apiFetchCart, addToCart as apiAddToCart, updateCartItem as apiUpdateCartItem, removeFromCart as apiRemoveFromCart } from "../api";
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

    const refreshCart = useCallback(async () => {
        if (!sessionId) return;
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

    const addItem = async (productId: string, variantId: string, quantity: number) => {
        try {
            await apiAddToCart({ productId, variantId, quantity });
            await refreshCart();
            addToast("Added to cart", "success");
        } catch (err) {
            addToast("Failed to add to cart", "error");
            throw err;
        }
    };

    const updateItemQuantity = async (itemId: string, quantity: number) => {
        const previousCart = cart;
        try {
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

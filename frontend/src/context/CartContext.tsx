import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
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

    const refreshCart = useCallback(async () => {
        if (!sessionId) return;
        try {
            setIsLoading(true);
            const data = await apiFetchCart();
            setCart(data);
        } catch (err) {
            console.error("Failed to fetch cart", err);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        refreshCart();
    }, [sessionId, user, refreshCart]);

    useEffect(() => {
        const handleRefresh = () => refreshCart();
        window.addEventListener("cart:refresh", handleRefresh);
        return () => window.removeEventListener("cart:refresh", handleRefresh);
    }, [refreshCart]);

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
        try {
            if (quantity < 1) {
                await apiRemoveFromCart(itemId);
                addToast("Item removed from cart", "info");
            } else {
                await apiUpdateCartItem(itemId, quantity);
            }
            await refreshCart();
        } catch (err) {
            addToast("Failed to update cart", "error");
            throw err;
        }
    };

    const removeItem = async (itemId: string) => {
        try {
            await apiRemoveFromCart(itemId);
            await refreshCart();
            addToast("Item removed from cart", "info");
        } catch (err) {
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

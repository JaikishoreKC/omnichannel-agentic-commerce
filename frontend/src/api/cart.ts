import { request } from "./client";
import type { Cart } from "../types";

export async function fetchCart(): Promise<Cart> {
    return request<Cart>("GET", "/cart");
}

export async function addToCart(input: {
    productId: string;
    variantId: string;
    quantity: number;
}): Promise<void> {
    await request("POST", "/cart/items", input);
}

export async function updateCartItem(
    itemId: string,
    quantity: number
): Promise<void> {
    await request("PUT", `/cart/items/${encodeURIComponent(itemId)}`, { quantity });
}

export async function removeFromCart(itemId: string): Promise<void> {
    await request("DELETE", `/cart/items/${encodeURIComponent(itemId)}`);
}

export async function applyDiscount(code: string): Promise<void> {
    await request("POST", `/cart/apply-discount`, { code });
}

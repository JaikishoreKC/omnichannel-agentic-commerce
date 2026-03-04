import { request } from "./client";
import type { Product } from "../types";

export interface PaginatedProducts {
    products: Product[];
    pagination: {
        page: number;
        limit: number;
        total: number;
        pages: number;
    };
}

export async function fetchProducts(options: {
    query?: string;
    category?: string;
    page?: number;
    limit?: number;
} = {}): Promise<PaginatedProducts> {
    const params = new URLSearchParams();
    if (options.query) params.append("query", options.query);
    if (options.category && options.category !== "All") params.append("category", options.category);
    if (options.page) params.append("page", options.page.toString());
    if (options.limit) params.append("limit", options.limit.toString());

    const queryString = params.toString();
    const url = `/products${queryString ? `?${queryString}` : ""}`;

    return request<PaginatedProducts>("GET", url);
}

export async function fetchProduct(productId: string): Promise<Product> {
    const data = await request<{ product: Product }>("GET", `/products/${encodeURIComponent(productId)}`);
    return data.product;
}

export async function addProductReview(productId: string, review: { rating: number, title?: string, comment?: string }): Promise<void> {
    await request("POST", `/products/${encodeURIComponent(productId)}/reviews`, review);
}

import { request } from "./client";

export interface AdminStats {
    totalRevenue: number;
    activeUsers: number;
    pendingOrders: number;
    totalProducts: number;
    revenueChange: string;
    userChange: string;
    orderChange: string;
    productChange: string;
}

export interface AdminOrder {
    id: string;
    userId: string;
    status: string;
    total: number;
    createdAt: string;
    items: Array<{ name: string; quantity: number }>;
}

export interface AdminProduct {
    id: string;
    name: string;
    category: string;
    price: number;
    status?: string;
    variants: Array<{ id: string; inStock: boolean }>;
}

export interface AdminUser {
    id: string;
    name: string;
    email: string;
    role: string;
    status?: string;
    createdAt: string;
}

export interface ActivityLog {
    id: string;
    adminId: string;
    adminEmail: string;
    action: string;
    resource: string;
    resourceId: string;
    timestamp: string;
    ipAddress?: string;
}

export async function getAdminStats(): Promise<AdminStats> {
    const res = await request<{
        users: { total: number };
        orders: { total: number; pending: number; revenue: number };
        interactions: { total: number };
        products: { total: number };
    }>("GET", "/admin/stats");

    return {
        totalRevenue: res.orders?.revenue ?? 0,
        activeUsers: res.users?.total ?? 0,
        pendingOrders: res.orders?.pending ?? 0,
        totalProducts: res.products?.total ?? 0,
        revenueChange: "+0%",
        userChange: `${res.users?.total ?? 0}`,
        orderChange: `${res.orders?.pending ?? 0}`,
        productChange: `${res.products?.total ?? 0}`,
    };
}

export async function getAdminOrders(limit = 10): Promise<AdminOrder[]> {
    const res = await request<{ orders: AdminOrder[] }>("GET", `/admin/orders?limit=${limit}`);
    return res.orders ?? [];
}

export async function getAdminProducts(limit = 20): Promise<AdminProduct[]> {
    const res = await request<{ products: AdminProduct[] }>("GET", `/admin/products?limit=${limit}`);
    return res.products ?? [];
}

export async function getAdminUsers(limit = 20): Promise<AdminUser[]> {
    const res = await request<{ users: AdminUser[] }>("GET", `/admin/users?limit=${limit}`);
    return res.users ?? [];
}

export async function getActivityLogs(limit = 20): Promise<ActivityLog[]> {
    const res = await request<{ logs: ActivityLog[] }>("GET", `/admin/activity?limit=${limit}`);
    return res.logs ?? [];
}

export async function createProduct(input: {
    name: string;
    description: string;
    category: string;
    price: number;
    currency?: string;
    variants?: Array<{ size: string; color: string; inStock: boolean }>;
}): Promise<AdminProduct> {
    return request<AdminProduct>("POST", "/admin/products", input);
}

export async function deleteProduct(productId: string): Promise<void> {
    return request<void>("DELETE", `/admin/products/${productId}`);
}

export async function verifyAdminIntegrity(): Promise<{ ok: boolean; total: number; issues: unknown[] }> {
    return request<{ ok: boolean; total: number; issues: unknown[] }>("GET", "/admin/activity/integrity");
}

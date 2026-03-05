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
    variants: Array<{ id: string; inStock: boolean; size?: string; color?: string }>;
}

export interface AdminCategory {
    id: string;
    slug: string;
    name: string;
    description?: string;
    status: string;
    createdAt?: string;
    updatedAt?: string;
}

export interface AdminInventory {
    variantId: string;
    productId: string;
    totalQuantity: number;
    reservedQuantity: number;
    availableQuantity: number;
    updatedAt?: string;
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

export interface AdminSupportTicket {
    id: string;
    userId?: string | null;
    sessionId?: string;
    issue: string;
    category: string;
    priority: string;
    status: string;
    updatedAt: string;
    createdAt: string;
}

export interface VoiceSettings {
    enabled?: boolean;
    killSwitch?: boolean;
    abandonmentMinutes?: number;
    maxAttemptsPerCart?: number;
    maxCallsPerUserPerDay?: number;
    maxCallsPerDay?: number;
    dailyBudgetUsd?: number;
    estimatedCostPerCallUsd?: number;
    quietHoursStart?: number;
    quietHoursEnd?: number;
    assistantId?: string;
    fromPhoneNumber?: string;
    defaultTimezone?: string;
    [key: string]: unknown;
}

export interface VoiceCall {
    id: string;
    userId?: string;
    status: string;
    createdAt?: string;
    updatedAt?: string;
}

export interface VoiceJob {
    id: string;
    userId?: string;
    status: string;
    createdAt?: string;
    updatedAt?: string;
}

export interface VoiceStats {
    [key: string]: unknown;
}

export interface HealthStatus {
    status: string;
    services: {
        llm: {
            enabled: boolean;
            provider: string;
            circuit_breaker?: string;
            circuitBreakerState?: string;
        };
        [key: string]: unknown;
    };
    [key: string]: unknown;
}

export async function getHealth(): Promise<HealthStatus> {
    const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/v1";
    const healthUrl = API_BASE.replace("/v1", "/health");
    const res = await fetch(healthUrl, { credentials: "include" });
    if (!res.ok) throw new Error("Failed to fetch health");
    return res.json();
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

export async function getAdminCategories(status?: string): Promise<AdminCategory[]> {
    const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await request<{ categories: AdminCategory[] }>("GET", `/admin/categories/records${suffix}`);
    return res.categories ?? [];
}

export async function createAdminCategory(input: {
    name: string;
    slug?: string;
    description?: string;
    status?: string;
}): Promise<AdminCategory> {
    const res = await request<{ category: AdminCategory }>("POST", "/admin/categories", input);
    return res.category;
}

export async function updateAdminCategory(
    categoryId: string,
    input: { name?: string; slug?: string; description?: string; status?: string },
): Promise<AdminCategory> {
    const res = await request<{ category: AdminCategory }>("PUT", `/admin/categories/${categoryId}`, input);
    return res.category;
}

export async function deleteAdminCategory(categoryId: string): Promise<void> {
    return request<void>("DELETE", `/admin/categories/${categoryId}`);
}

export async function getAdminInventory(variantId: string): Promise<AdminInventory> {
    const res = await request<{ inventory: AdminInventory }>("GET", `/admin/inventory/${variantId}`);
    return res.inventory;
}

export async function updateAdminInventory(
    variantId: string,
    input: { totalQuantity?: number; availableQuantity?: number },
): Promise<AdminInventory> {
    const res = await request<{ inventory: AdminInventory }>("PUT", `/admin/inventory/${variantId}`, input);
    return res.inventory;
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

export async function getAdminSupportTickets(params?: {
    status?: string;
    userId?: string;
    limit?: number;
}): Promise<AdminSupportTicket[]> {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.userId) search.set("userId", params.userId);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    const res = await request<{ tickets: AdminSupportTicket[] }>("GET", `/admin/support/tickets${suffix}`);
    return res.tickets ?? [];
}

export async function updateAdminSupportTicket(
    ticketId: string,
    input: { status?: string; priority?: string; note?: string },
): Promise<AdminSupportTicket> {
    const res = await request<{ ticket: AdminSupportTicket }>("PATCH", `/admin/support/tickets/${ticketId}`, input);
    return res.ticket;
}

export async function getVoiceSettings(): Promise<VoiceSettings> {
    const res = await request<{ settings: VoiceSettings }>("GET", "/admin/voice/settings");
    return res.settings ?? {};
}

export async function updateVoiceSettings(input: VoiceSettings): Promise<VoiceSettings> {
    const res = await request<{ settings: VoiceSettings }>("PUT", "/admin/voice/settings", input);
    return res.settings ?? {};
}

export async function runVoiceRecoveryProcess(): Promise<Record<string, unknown>> {
    const res = await request<{ result: Record<string, unknown> }>("POST", "/admin/voice/process");
    return res.result ?? {};
}

export async function getVoiceCalls(limit = 50, status?: string): Promise<VoiceCall[]> {
    const search = new URLSearchParams({ limit: String(limit) });
    if (status) search.set("status", status);
    const res = await request<{ calls: VoiceCall[] }>("GET", `/admin/voice/calls?${search.toString()}`);
    return res.calls ?? [];
}

export async function getVoiceJobs(limit = 50, status?: string): Promise<VoiceJob[]> {
    const search = new URLSearchParams({ limit: String(limit) });
    if (status) search.set("status", status);
    const res = await request<{ jobs: VoiceJob[] }>("GET", `/admin/voice/jobs?${search.toString()}`);
    return res.jobs ?? [];
}

export async function getVoiceStats(): Promise<VoiceStats> {
    const res = await request<{ stats: VoiceStats }>("GET", "/admin/voice/stats");
    return res.stats ?? {};
}

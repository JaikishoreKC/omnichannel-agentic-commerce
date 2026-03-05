import { request } from "./client";

export interface SupportMessage {
    actor: string;
    message: string;
    timestamp: string;
}

export interface SupportTicket {
    id: string;
    userId?: string | null;
    sessionId: string;
    issue: string;
    category: string;
    priority: string;
    status: string;
    channel: string;
    messages: SupportMessage[];
    resolution?: string | null;
    createdAt: string;
    updatedAt: string;
}

export async function listSupportTickets(params?: {
    status?: string;
    limit?: number;
}): Promise<SupportTicket[]> {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    const res = await request<{ tickets: SupportTicket[] }>("GET", `/support/tickets${suffix}`);
    return res.tickets ?? [];
}

export async function createSupportTicket(input: {
    issue: string;
    priority?: string;
    category?: string;
    channel?: string;
}): Promise<SupportTicket> {
    const res = await request<{ ticket: SupportTicket }>("POST", "/support/tickets", input);
    return res.ticket;
}

export async function updateSupportTicket(
    ticketId: string,
    input: { status?: string; note?: string },
): Promise<SupportTicket> {
    const res = await request<{ ticket: SupportTicket }>("PATCH", `/support/tickets/${ticketId}`, input);
    return res.ticket;
}

import { request } from "./client";

export interface MemoryPreferences {
    size: string | null;
    brandPreferences: string[];
    categories: string[];
    stylePreferences: string[];
    colorPreferences: string[];
    priceRange: {
        min: number;
        max: number;
    };
}

export interface MemorySnapshot {
    preferences: MemoryPreferences;
    interactionHistory: Array<Record<string, unknown>>;
    productAffinities: Record<string, unknown>;
    updatedAt: string;
}

export interface MemoryHistoryEvent {
    id: string;
    userId: string;
    eventType: string;
    key: string;
    value: unknown;
    oldValue: unknown;
    source: string;
    timestamp: string;
}

export async function fetchMemory(): Promise<MemorySnapshot> {
    return request<MemorySnapshot>("GET", "/memory");
}

export async function updateMemoryPreferences(updates: Partial<MemoryPreferences>): Promise<void> {
    await request("PUT", "/memory/preferences", updates);
}

export async function fetchMemoryHistory(limit: number = 20): Promise<{ history: MemoryHistoryEvent[] }> {
    return request<{ history: MemoryHistoryEvent[] }>("GET", `/memory/history?limit=${limit}`);
}

export async function deleteMemoryPreference(key: string, value?: string): Promise<void> {
    const query = value ? `?value=${encodeURIComponent(value)}` : "";
    await request("DELETE", `/memory/preferences/${encodeURIComponent(key)}${query}`);
}

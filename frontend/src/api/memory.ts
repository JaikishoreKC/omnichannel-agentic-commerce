import { request } from "./client";

export interface MemorySnapshot {
    snapshot: {
        preferences: Record<string, string>;
        flags: Record<string, unknown>;
        lastUpdated: string;
    }
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

export async function updateMemoryPreferences(updates: Record<string, string>): Promise<void> {
    await request("PUT", "/memory/preferences", { preferences: updates });
}

export async function fetchMemoryHistory(limit: number = 20): Promise<{ events: MemoryHistoryEvent[] }> {
    return request<{ events: MemoryHistoryEvent[] }>("GET", `/memory/history?limit=${limit}`);
}

export async function deleteMemoryPreference(key: string): Promise<void> {
    await request("DELETE", `/memory/preferences/${encodeURIComponent(key)}`);
}

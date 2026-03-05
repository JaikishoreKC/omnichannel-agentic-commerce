import { request } from "./client";
import type { AuthResponse } from "../types";

type ProfileAddress = {
    name: string;
    line1: string;
    line2?: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
};

export async function register(input: {
    email: string;
    password: string;
    name: string;
    phone?: string;
    timezone?: string;
}): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/auth/register", input);
}

export async function login(input: {
    email: string;
    password: string;
    otp?: string;
}): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/auth/login", input);
}

export async function refreshToken(input?: { refreshToken?: string }): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/auth/refresh", input ?? {});
}

export async function logout(): Promise<void> {
    await request<void>("POST", "/auth/logout", {});
}

export async function getProfile(): Promise<{ user: AuthResponse["user"] }> {
    return request<{ user: AuthResponse["user"] }>("GET", "/auth/profile");
}

export async function updateProfile(input: {
    name?: string;
    phone?: string;
    timezone?: string;
    defaultShippingAddress?: ProfileAddress;
}): Promise<{ user: AuthResponse["user"] }> {
    return request<{ user: AuthResponse["user"] }>("PATCH", "/auth/profile", input);
}

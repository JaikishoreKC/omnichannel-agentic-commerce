import { request } from "./client";
import type { AuthResponse } from "../types";

export async function register(input: {
    email: string;
    password: string;
    name: string;
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

export async function refreshToken(input: { refreshToken: string }): Promise<AuthResponse> {
    return request<AuthResponse>("POST", "/auth/refresh", input);
}

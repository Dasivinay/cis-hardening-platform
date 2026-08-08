import { apiClient } from "./client";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "analyst" | "viewer";
  is_active: boolean;
}

export async function login(email: string, password: string) {
  const { data } = await apiClient.post("/auth/login", { email, password });
  return data as { access_token: string; refresh_token: string; user: User };
}

export async function register(email: string, password: string, full_name: string) {
  const { data } = await apiClient.post("/auth/register", { email, password, full_name });
  return data as User;
}

export async function fetchMe() {
  const { data } = await apiClient.get("/auth/me");
  return data as User;
}

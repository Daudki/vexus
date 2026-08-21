import { apiRequest, setAccessToken } from "./api";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  role: "admin" | "security_analyst" | "network_administrator" | "viewer";
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export async function login(username: string, password: string): Promise<CurrentUser> {
  const tokens = await apiRequest<TokenPair>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setAccessToken(tokens.access_token);
  sessionStorage.setItem("vexus_refresh_token", tokens.refresh_token);
  return fetchCurrentUser();
}

export function logout(): void {
  setAccessToken(null);
  sessionStorage.removeItem("vexus_refresh_token");
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>("/auth/me");
}

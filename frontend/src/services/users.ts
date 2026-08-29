import { apiRequest } from "./api";

export type Role = "admin" | "security_analyst" | "network_administrator" | "viewer";

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface CreateUserPayload {
  username: string;
  email: string;
  password: string;
  role: Role;
}

export function listUsers(): Promise<AdminUser[]> {
  return apiRequest<AdminUser[]>("/users");
}

export function createUser(payload: CreateUserPayload): Promise<AdminUser> {
  return apiRequest<AdminUser>("/users", { method: "POST", body: JSON.stringify(payload) });
}

export function updateUserRole(userId: string, role: Role): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/users/${userId}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
}

export function setUserActive(userId: string, isActive: boolean): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function resetUserPassword(userId: string, newPassword: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export function deleteUser(userId: string): Promise<void> {
  return apiRequest<void>(`/users/${userId}`, { method: "DELETE" });
}

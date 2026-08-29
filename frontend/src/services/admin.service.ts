import { apiRequest } from './api'

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: string[]
  permissions: string[]
  created_at: string
  last_login?: string
}

export interface Role {
  id: string
  name: string
  description: string
  permissions: string[]
  created_at: string
}

export interface AuditLog {
  id: string
  user_id: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  details: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  timestamp: string
}

export interface SystemSettings {
  allow_registration: boolean
  require_email_verification: boolean
  default_role: string
  session_timeout_minutes: number
  max_login_attempts: number
  lockout_duration_minutes: number
  scan_ranges: string[]
}

export const adminService = {
  // Users
  async getUsers(params?: { skip?: number; limit?: number; include_inactive?: boolean }): Promise<{ items: User[]; total: number }> {
    const query = new URLSearchParams()
    if (params?.skip) query.set('skip', String(params.skip))
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.include_inactive) query.set('include_inactive', String(params.include_inactive))
    const url = `/admin/users${query.toString() ? `?${query.toString()}` : ''}`
    return apiRequest<{ items: User[]; total: number }>(url)
  },

  async getUser(id: string): Promise<User> {
    return apiRequest<User>(`/admin/users/${id}`)
  },

  async createUser(data: Partial<User> & { password: string }): Promise<User> {
    return apiRequest<User>('/admin/users', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateUser(id: string, data: Partial<User>): Promise<User> {
    return apiRequest<User>(`/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteUser(id: string): Promise<void> {
    return apiRequest<void>(`/admin/users/${id}`, {
      method: 'DELETE',
    })
  },

  async toggleUserActive(id: string): Promise<User> {
    return apiRequest<User>(`/admin/users/${id}/toggle-active`, {
      method: 'PATCH',
    })
  },

  // Roles
  async getRoles(): Promise<Role[]> {
    return apiRequest<Role[]>('/admin/roles')
  },

  async getRole(id: string): Promise<Role> {
    return apiRequest<Role>(`/admin/roles/${id}`)
  },

  async createRole(data: Partial<Role>): Promise<Role> {
    return apiRequest<Role>('/admin/roles', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateRole(id: string, data: Partial<Role>): Promise<Role> {
    return apiRequest<Role>(`/admin/roles/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteRole(id: string): Promise<void> {
    return apiRequest<void>(`/admin/roles/${id}`, {
      method: 'DELETE',
    })
  },

  // Audit Logs
  async getAuditLogs(params?: {
    action?: string
    user_id?: string
    start_date?: string
    end_date?: string
    skip?: number
    limit?: number
  }): Promise<{ items: AuditLog[]; total: number }> {
    const query = new URLSearchParams()
    if (params?.action) query.set('action', params.action)
    if (params?.user_id) query.set('user_id', params.user_id)
    if (params?.start_date) query.set('start_date', params.start_date)
    if (params?.end_date) query.set('end_date', params.end_date)
    if (params?.skip) query.set('skip', String(params.skip))
    if (params?.limit) query.set('limit', String(params.limit))
    const url = `/admin/audit${query.toString() ? `?${query.toString()}` : ''}`
    return apiRequest<{ items: AuditLog[]; total: number }>(url)
  },

  // Settings
  async getSettings(): Promise<SystemSettings> {
    return apiRequest<SystemSettings>('/admin/settings')
  },

  async updateSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    return apiRequest<SystemSettings>('/admin/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  // System
  async getSystemStats(): Promise<{
    total_users: number
    active_users: number
    total_assets: number
    active_assets: number
    total_alerts: number
    new_alerts: number
    total_incidents: number
    open_incidents: number
    health_status: string
  }> {
    return apiRequest('/admin/stats')
  },
}
import { apiRequest, setAccessToken } from './api'

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
}

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: string[]
  permissions: string[]
  created_at: string
}

export const authService = {
  async login(data: LoginRequest): Promise<LoginResponse> {
    const response = await apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    })
    if (response.access_token) {
      setAccessToken(response.access_token)
    }
    return response
  },

  async refreshToken(refreshToken: string): Promise<{ access_token: string }> {
    const response = await apiRequest<{ access_token: string }>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (response.access_token) {
      setAccessToken(response.access_token)
    }
    return response
  },

  async logout(): Promise<void> {
    try {
      await apiRequest<void>('/auth/logout', { method: 'POST' })
    } finally {
      setAccessToken(null)
    }
  },

  async getCurrentUser(): Promise<User> {
    return apiRequest<User>('/auth/me')
  },
}
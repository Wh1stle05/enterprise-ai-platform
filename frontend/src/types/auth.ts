export interface User {
  id: string
  username: string
  email: string
  display_name: string | null
  is_superuser: boolean
  created_at: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

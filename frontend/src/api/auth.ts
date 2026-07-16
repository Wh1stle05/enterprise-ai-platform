import client from './client'
import type { RegisterRequest, LoginRequest, TokenResponse, User } from '../types/auth'

export async function register(data: RegisterRequest): Promise<TokenResponse> {
  const res = await client.post('/auth/register', data)
  return res.data
}

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await client.post('/auth/login', data)
  return res.data
}

export async function getMe(): Promise<User> {
  const res = await client.get('/auth/me')
  return res.data
}

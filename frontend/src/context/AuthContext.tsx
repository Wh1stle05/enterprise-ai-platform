import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import type { User } from '../types/auth'
import { getMe } from '../api/auth'

export interface AuthContextType {
  user: User | null
  token: string | null
  loading: boolean
  loginUser: (token: string, user: User) => void
  logout: () => void
  refresh: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    const t = localStorage.getItem('token')
    if (!t) {
      setUser(null)
      setToken(null)
      setLoading(false)
      return
    }
    try {
      setToken(t)
      const u = await getMe()
      setUser(u)
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      setUser(null)
      setToken(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const loginUser = (t: string, u: User) => {
    localStorage.setItem('token', t)
    localStorage.setItem('user', JSON.stringify(u))
    setToken(t)
    setUser(u)
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, loginUser, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

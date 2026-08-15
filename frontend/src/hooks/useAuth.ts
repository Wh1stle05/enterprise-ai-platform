import { useContext } from 'react'
import { AuthContext, type AuthContextType } from '../context/AuthContext'

export function useAuth(): AuthContextType {
  return useContext(AuthContext)
}

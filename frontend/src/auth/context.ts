import { createContext, useContext } from 'react'

import type { AccountProfile } from '../api/auth'

export type AuthStatus = 'loading' | 'signedIn' | 'signedOut'

export interface AuthContextValue {
  status: AuthStatus
  user: AccountProfile | undefined
  login(email: string, password: string): Promise<void>
  logout(): Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export const ME_QUERY_KEY = ['me'] as const

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

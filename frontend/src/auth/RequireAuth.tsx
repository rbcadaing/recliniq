import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from './context'

/** Renders children for signed-in users; otherwise sends them to /login and back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <output className="page__muted">Loading your account…</output>
  }
  if (status === 'signedOut') {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return children
}

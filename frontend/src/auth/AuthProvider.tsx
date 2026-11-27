import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from 'react'

import { getMe, login as loginRequest, logout as logoutRequest } from '../api/auth'
import { AuthContext, type AuthStatus, ME_QUERY_KEY } from './context'
import { refreshSession } from './refresh'
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  setSession,
  subscribe,
  watchOtherTabs,
} from './session'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const accessToken = useSyncExternalStore(subscribe, getAccessToken)
  // On load the access token is gone (memory only); restore it from the stored refresh token.
  const [restoring, setRestoring] = useState(() => getAccessToken() === null && !!getRefreshToken())

  useEffect(() => watchOtherTabs(), [])

  useEffect(() => {
    if (!restoring) return
    let active = true
    void refreshSession().finally(() => {
      if (active) setRestoring(false)
    })
    return () => {
      active = false
    }
  }, [restoring])

  const me = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: () => getMe(),
    enabled: accessToken !== null,
    staleTime: 60_000,
    retry: false,
  })

  useEffect(() => {
    if (accessToken === null) queryClient.removeQueries({ queryKey: ME_QUERY_KEY })
  }, [accessToken, queryClient])

  const login = useCallback(
    async (email: string, password: string) => {
      setSession(await loginRequest(email, password))
      await queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY })
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken()
    clearSession()
    queryClient.removeQueries({ queryKey: ME_QUERY_KEY })
    if (refreshToken) {
      // Best effort: the local session is already gone even if the network call fails.
      await logoutRequest(refreshToken).catch(() => undefined)
    }
  }, [queryClient])

  let status: AuthStatus = 'signedOut'
  if (restoring || (accessToken !== null && me.isPending)) status = 'loading'
  else if (accessToken !== null && me.isSuccess) status = 'signedIn'

  const value = useMemo(
    () => ({ status, user: status === 'signedIn' ? me.data : undefined, login, logout }),
    [status, me.data, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

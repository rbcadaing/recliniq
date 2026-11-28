import type { TokenResponse } from '../api/auth'
import { API_BASE_URL, ApiError, createApiClient } from '../api/client'
import type { components } from '../api/generated/schema'
import { clearSession, getRefreshToken, setSession } from './session'

const LOCK_NAME = 'recliniq-refresh'

let inflight: Promise<boolean> | null = null

/**
 * Exchange the stored refresh token for a new pair. Resolves true when a new access token is
 * available.
 *
 * - Single-flight within the tab: concurrent 401s share one refresh.
 * - Across tabs: the Web Locks API serializes refreshes, and the token is read *inside* the lock,
 *   so a tab always uses the newest one. Without this, two tabs could present the same token,
 *   the backend would see reuse, and it would revoke the session.
 * - If the backend rejects the token, the session is cleared. Network errors keep it.
 */
export function refreshSession(): Promise<boolean> {
  inflight ??= withLock(exchange).finally(() => {
    inflight = null
  })
  return inflight
}

async function withLock<T>(task: () => Promise<T>): Promise<T> {
  const locks = globalThis.navigator?.locks
  if (!locks) return task()
  return locks.request(LOCK_NAME, task)
}

async function exchange(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  // A plain client: no auth hooks, so a failing refresh can't trigger another refresh.
  const client = createApiClient(API_BASE_URL)
  try {
    const tokens = await client.post<TokenResponse>('/api/v1/auth/refresh', {
      refresh_token: refreshToken,
    } satisfies components['schemas']['RefreshRequest'])
    setSession(tokens)
    return true
  } catch (error) {
    if (error instanceof ApiError && error.kind === 'http' && error.status === 401) {
      clearSession()
    }
    return false
  }
}

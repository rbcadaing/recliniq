/**
 * Session token store.
 * - Access token: memory only (gone on reload; re-obtained with the refresh token).
 * - Refresh token: localStorage, so a reload keeps the user signed in. Falls back to memory when
 *   storage is unavailable (private mode, blocked site data).
 */

const REFRESH_KEY = 'recliniq.refreshToken'

let accessToken: string | null = null
let memoryRefreshToken: string | null = null
const listeners = new Set<() => void>()

export interface TokenPair {
  access_token: string
  refresh_token: string
}

function notify() {
  for (const listener of listeners) listener()
}

function readStoredRefresh(): string | null {
  try {
    return globalThis.localStorage.getItem(REFRESH_KEY)
  } catch {
    return memoryRefreshToken
  }
}

function writeStoredRefresh(value: string | null) {
  memoryRefreshToken = value
  try {
    if (value === null) globalThis.localStorage.removeItem(REFRESH_KEY)
    else globalThis.localStorage.setItem(REFRESH_KEY, value)
  } catch {
    // Storage unavailable: the memory copy is used instead (no persistence across reloads).
  }
}

export function getAccessToken(): string | null {
  return accessToken
}

export function getRefreshToken(): string | null {
  return readStoredRefresh()
}

export function hasSession(): boolean {
  return getRefreshToken() !== null
}

export function setSession(tokens: TokenPair) {
  accessToken = tokens.access_token
  writeStoredRefresh(tokens.refresh_token)
  notify()
}

export function clearSession() {
  accessToken = null
  writeStoredRefresh(null)
  notify()
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Another tab signed out (refresh token removed): drop this tab's access token too. */
export function watchOtherTabs(): () => void {
  function onStorage(event: StorageEvent) {
    if (event.key === REFRESH_KEY && event.newValue === null && accessToken !== null) {
      accessToken = null
      notify()
    }
  }
  globalThis.addEventListener('storage', onStorage)
  return () => globalThis.removeEventListener('storage', onStorage)
}

/** Test helper: forget everything, including the memory fallback. */
export function resetSessionForTests() {
  accessToken = null
  memoryRefreshToken = null
  try {
    globalThis.localStorage.removeItem(REFRESH_KEY)
  } catch {
    // ignore
  }
}

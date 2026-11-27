import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from '../api/client'
import { apiError, json, mockApi } from '../test/mockApi'
import { refreshSession } from './refresh'
import { clearSession, getAccessToken, getRefreshToken, setSession } from './session'

const PAIR = { access_token: 'access-1', refresh_token: 'refresh-1' }

describe('session store', () => {
  it('keeps the access token in memory and the refresh token in localStorage', () => {
    setSession(PAIR)

    expect(getAccessToken()).toBe('access-1')
    expect(localStorage.getItem('recliniq.refreshToken')).toBe('refresh-1')
    expect(JSON.stringify(localStorage)).not.toContain('access-1')

    clearSession()
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('falls back to memory when storage throws', () => {
    const blocked = () => {
      throw new DOMException('blocked', 'SecurityError')
    }
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(blocked)
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(blocked)
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(blocked)

    setSession(PAIR)
    expect(getRefreshToken()).toBe('refresh-1')
    clearSession()
    expect(getRefreshToken()).toBeNull()
  })
})

describe('API client auth hooks', () => {
  function hooks(token: string | null, refreshResult = true) {
    let current = token
    return {
      getAccessToken: () => current,
      refresh: vi.fn<() => Promise<boolean>>(async () => {
        current = 'fresh-token'
        return refreshResult
      }),
    }
  }

  it('sends the access token as a bearer header', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(json({ ok: true }))
    const client = createApiClient('http://api.test', fetchMock, hooks('abc'))

    await client.get('/api/v1/me')

    const headers = new Headers(fetchMock.mock.calls[0]![1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer abc')
  })

  it('refreshes once on 401 and retries with the new token', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(apiError(401, 'not_authenticated', 'Sign in to continue.'))
      .mockResolvedValueOnce(json({ id: 'u1' }))
    const auth = hooks('expired')
    const client = createApiClient('http://api.test', fetchMock, auth)

    await expect(client.get('/api/v1/me')).resolves.toEqual({ id: 'u1' })

    expect(auth.refresh).toHaveBeenCalledTimes(1)
    const retryHeaders = new Headers(fetchMock.mock.calls[1]![1]?.headers)
    expect(retryHeaders.get('Authorization')).toBe('Bearer fresh-token')
  })

  it('gives up after one retry, and when the refresh fails', async () => {
    const unauthorized = () => apiError(401, 'not_authenticated', 'Sign in to continue.')
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async () => unauthorized())

    const auth = hooks('expired')
    const client = createApiClient('http://api.test', fetchMock, auth)
    await expect(client.get('/api/v1/me')).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).toHaveBeenCalledTimes(2)

    fetchMock.mockClear()
    const failing = hooks('expired', false)
    const client2 = createApiClient('http://api.test', fetchMock, failing)
    await expect(client2.get('/api/v1/me')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('never refreshes for auth endpoints', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(apiError(401, 'invalid_credentials', 'Incorrect email or password.'))
    const auth = hooks(null)
    const client = createApiClient('http://api.test', fetchMock, auth)

    await expect(client.post('/api/v1/auth/login', {})).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(auth.refresh).not.toHaveBeenCalled()
  })
})

describe('refreshSession', () => {
  it('rotates the stored tokens', async () => {
    setSession(PAIR)
    const calls = mockApi({
      'POST /api/v1/auth/refresh': () =>
        json({ access_token: 'access-2', refresh_token: 'refresh-2' }),
    })

    await expect(refreshSession()).resolves.toBe(true)

    expect(calls[0]?.body).toEqual({ refresh_token: 'refresh-1' })
    expect(getAccessToken()).toBe('access-2')
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('shares one request between concurrent callers', async () => {
    setSession(PAIR)
    const calls = mockApi({
      'POST /api/v1/auth/refresh': () =>
        json({ access_token: 'access-2', refresh_token: 'refresh-2' }),
    })

    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()])

    expect(results).toEqual([true, true, true])
    expect(calls).toHaveLength(1)
  })

  it('clears the session when the backend rejects the refresh token', async () => {
    setSession(PAIR)
    mockApi({
      'POST /api/v1/auth/refresh': () =>
        apiError(401, 'invalid_refresh_token', 'Your session has expired.'),
    })

    await expect(refreshSession()).resolves.toBe(false)

    expect(getRefreshToken()).toBeNull()
    expect(getAccessToken()).toBeNull()
  })

  it('keeps the session on a network error', async () => {
    setSession(PAIR)
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(refreshSession()).resolves.toBe(false)

    expect(getRefreshToken()).toBe('refresh-1')
  })

  it('runs inside the cross-tab lock and reads the token there', async () => {
    setSession(PAIR)
    const request = vi.fn<(name: string, task: () => Promise<unknown>) => Promise<unknown>>(
      async (_name, task) => {
        // Another tab rotated the token while this one waited for the lock.
        localStorage.setItem('recliniq.refreshToken', 'refresh-from-other-tab')
        return task()
      },
    )
    vi.stubGlobal('navigator', { ...navigator, locks: { request } })
    const calls = mockApi({
      'POST /api/v1/auth/refresh': () =>
        json({ access_token: 'access-3', refresh_token: 'refresh-3' }),
    })

    await expect(refreshSession()).resolves.toBe(true)

    expect(request).toHaveBeenCalledWith('recliniq-refresh', expect.any(Function))
    expect(calls[0]?.body).toEqual({ refresh_token: 'refresh-from-other-tab' })
    vi.unstubAllGlobals()
  })

  it('does nothing without a stored refresh token', async () => {
    const calls = mockApi({})
    await expect(refreshSession()).resolves.toBe(false)
    expect(calls).toHaveLength(0)
  })
})

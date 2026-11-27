/**
 * The single entry point for calling the backend. Every request goes through here so the base
 * URL, request IDs, and error normalization stay consistent.
 */

import { refreshSession } from '../auth/refresh'
import { getAccessToken } from '../auth/session'

export type ApiErrorKind = 'http' | 'network'

interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details?: unknown
    request_id?: string | null
  }
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | undefined
  readonly code: string
  readonly details: unknown
  readonly requestId: string | undefined
  /** Seconds to wait before retrying, from the `Retry-After` header (429 responses). */
  readonly retryAfter: number | undefined

  constructor(options: {
    kind: ApiErrorKind
    message: string
    code: string
    status?: number
    details?: unknown
    requestId?: string
    retryAfter?: number
    cause?: unknown
  }) {
    super(options.message, { cause: options.cause })
    this.name = 'ApiError'
    this.kind = options.kind
    this.status = options.status
    this.code = options.code
    this.details = options.details
    this.requestId = options.requestId
    this.retryAfter = options.retryAfter
  }
}

export interface ApiClient {
  get<T>(path: string, init?: RequestInit): Promise<T>
  /** POST `body` as JSON. */
  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>
  request<T>(path: string, init?: RequestInit): Promise<T>
}

const REQUEST_ID_HEADER = 'X-Request-ID'

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = (value as { error: unknown }).error
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  )
}

function parseRetryAfter(value: string | null): number | undefined {
  if (value === null) return undefined
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined
}

function newRequestId(): string {
  return globalThis.crypto.randomUUID().replaceAll('-', '')
}

/** Optional session hooks: attach the access token and recover once from an expired one. */
export interface AuthHooks {
  getAccessToken(): string | null
  /** Refresh the session; resolves true if a new access token is available. */
  refresh(): Promise<boolean>
}

// Auth endpoints answer 401 for wrong credentials or dead refresh tokens; never retry those.
const AUTH_PATH = /^\/api\/v1\/auth\//

export function createApiClient(
  baseUrl: string,
  fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args),
  auth?: AuthHooks,
): ApiClient {
  const root = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    try {
      return await send<T>(path, init)
    } catch (error) {
      const canRetry =
        auth && error instanceof ApiError && error.status === 401 && !AUTH_PATH.test(path)
      if (canRetry && (await auth.refresh())) return send<T>(path, init)
      throw error
    }
  }

  async function send<T>(path: string, init: RequestInit): Promise<T> {
    const requestId = newRequestId()
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    headers.set(REQUEST_ID_HEADER, requestId)
    if (init.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const accessToken = auth?.getAccessToken()
    if (accessToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${accessToken}`)
    }

    let response: Response
    try {
      response = await fetchImpl(`${root}${path}`, { ...init, headers })
    } catch (cause) {
      throw new ApiError({
        kind: 'network',
        code: 'network_error',
        message: 'Unable to reach the server. Check your connection and try again.',
        requestId,
        cause,
      })
    }

    const responseRequestId = response.headers.get(REQUEST_ID_HEADER) ?? requestId
    const body: unknown = await response.json().catch(() => undefined)

    if (!response.ok) {
      const retryAfter = parseRetryAfter(response.headers.get('Retry-After'))
      if (isErrorEnvelope(body)) {
        throw new ApiError({
          kind: 'http',
          status: response.status,
          code: body.error.code,
          message: body.error.message,
          details: body.error.details,
          requestId: body.error.request_id ?? responseRequestId,
          retryAfter,
        })
      }
      throw new ApiError({
        kind: 'http',
        status: response.status,
        code: 'http_error',
        message: `Request failed with status ${response.status}.`,
        requestId: responseRequestId,
        retryAfter,
      })
    }

    return body as T
  }

  return {
    request,
    get: (path, init) => request(path, { ...init, method: 'GET' }),
    post: (path, body, init) =>
      request(path, {
        ...init,
        method: 'POST',
        body: body === undefined ? undefined : JSON.stringify(body),
      }),
  }
}

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

/** The app-wide client: sends the session's access token and refreshes it once on 401. */
export const api = createApiClient(API_BASE_URL, undefined, {
  // Wrapped so the session modules are only touched at call time (they import this module).
  getAccessToken: () => getAccessToken(),
  refresh: () => refreshSession(),
})

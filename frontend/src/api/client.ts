/**
 * The single entry point for calling the backend. Every request goes through here so the base
 * URL, request IDs, and error normalization stay consistent.
 */

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

  constructor(options: {
    kind: ApiErrorKind
    message: string
    code: string
    status?: number
    details?: unknown
    requestId?: string
    cause?: unknown
  }) {
    super(options.message, { cause: options.cause })
    this.name = 'ApiError'
    this.kind = options.kind
    this.status = options.status
    this.code = options.code
    this.details = options.details
    this.requestId = options.requestId
  }
}

export interface ApiClient {
  get<T>(path: string, init?: RequestInit): Promise<T>
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

function newRequestId(): string {
  return globalThis.crypto.randomUUID().replaceAll('-', '')
}

export function createApiClient(
  baseUrl: string,
  fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args),
): ApiClient {
  const root = baseUrl.replace(/\/+$/, '')

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const requestId = newRequestId()
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    headers.set(REQUEST_ID_HEADER, requestId)
    if (init.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
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
      if (isErrorEnvelope(body)) {
        throw new ApiError({
          kind: 'http',
          status: response.status,
          code: body.error.code,
          message: body.error.message,
          details: body.error.details,
          requestId: body.error.request_id ?? responseRequestId,
        })
      }
      throw new ApiError({
        kind: 'http',
        status: response.status,
        code: 'http_error',
        message: `Request failed with status ${response.status}.`,
        requestId: responseRequestId,
      })
    }

    return body as T
  }

  return {
    request,
    get: (path, init) => request(path, { ...init, method: 'GET' }),
  }
}

export const api = createApiClient(import.meta.env.VITE_API_BASE_URL ?? '')

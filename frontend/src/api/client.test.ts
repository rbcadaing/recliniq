import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from './client'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('createApiClient', () => {
  it('prefixes requests with the configured base URL and sends a request ID', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ status: 'ok' }))
    const client = createApiClient('http://api.test/', fetchMock)

    const result = await client.get<{ status: string }>('/api/v1/health')

    expect(result).toEqual({ status: 'ok' })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('http://api.test/api/v1/health')
    const headers = new Headers(init?.headers)
    expect(headers.get('X-Request-ID')).toMatch(/^[a-f0-9]{32}$/)
    expect(init?.method).toBe('GET')
  })

  it('normalizes the backend error envelope into an ApiError', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: 'not_found',
            message: 'Patient not found.',
            details: null,
            request_id: 'req-42',
          },
        },
        { status: 404 },
      ),
    )
    const client = createApiClient('http://api.test', fetchMock)

    const error = await client.get('/api/v1/patients/1').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      kind: 'http',
      status: 404,
      code: 'not_found',
      message: 'Patient not found.',
      requestId: 'req-42',
    })
  })

  it('handles non-envelope error responses', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('<html>bad gateway</html>', {
        status: 502,
        headers: { 'X-Request-ID': 'gw-1' },
      }),
    )
    const client = createApiClient('http://api.test', fetchMock)

    const error = await client.get('/api/v1/health').catch((e: unknown) => e)

    expect(error).toMatchObject({
      kind: 'http',
      status: 502,
      code: 'http_error',
      requestId: 'gw-1',
    })
  })

  it('raises a network ApiError when the server cannot be reached', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = createApiClient('http://api.test', fetchMock)

    const error = await client.get('/api/v1/health').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ kind: 'network', code: 'network_error', status: undefined })
  })

  it('posts JSON bodies with a content type', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ message: 'ok' }))
    const client = createApiClient('http://api.test', fetchMock)

    await client.post('/api/v1/things', { name: 'x' })

    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('http://api.test/api/v1/things')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe('{"name":"x"}')
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json')
  })

  it('exposes Retry-After seconds on rate-limited errors', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse(
          { error: { code: 'too_many_requests', message: 'Too many attempts.' } },
          { status: 429, headers: { 'Content-Type': 'application/json', 'Retry-After': '120' } },
        ),
      )
    const client = createApiClient('http://api.test', fetchMock)

    const error = await client.post('/api/v1/things', {}).catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 429, code: 'too_many_requests', retryAfter: 120 })
  })
})

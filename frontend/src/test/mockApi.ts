import { vi } from 'vitest'

export interface Call {
  method: string
  path: string
  body: unknown
}

type Handler = (call: Call) => Response | Promise<Response>

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

export function apiError(
  status: number,
  code: string,
  message: string,
  details: unknown = null,
  headers: Record<string, string> = {},
): Response {
  return json({ error: { code, message, details, request_id: 'req-1' } }, status, headers)
}

/** Stub `fetch` with handlers keyed by `"METHOD /path"`; records every call. */
export function mockApi(handlers: Record<string, Handler>) {
  const calls: Call[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://localhost')
    const method = (init?.method ?? 'GET').toUpperCase()
    const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
    const call = { method, path: url.pathname, body }
    calls.push(call)
    const handler = handlers[`${method} ${url.pathname}`]
    if (!handler) return apiError(404, 'not_found', `No mock for ${method} ${url.pathname}`)
    return handler(call)
  })
  return calls
}

export const SPECIALIZATIONS = [
  { id: '11111111-1111-1111-1111-111111111111', code: 'cardiology', name: 'Cardiology' },
  { id: '22222222-2222-2222-2222-222222222222', code: 'pediatrics', name: 'Pediatrics' },
]

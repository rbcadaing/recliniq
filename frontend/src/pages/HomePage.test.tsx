import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderAt } from '../test/render'

describe('HomePage backend status', () => {
  it('shows the backend as online with its version when the health check succeeds', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', name: 'RecliniQ', version: '1.2.3' }), {
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    renderAt('/')

    expect(await screen.findByText(/online · v1\.2\.3/i)).toBeInTheDocument()
  })

  it('shows the backend as offline when the health check fails, without crashing', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    renderAt('/')

    expect(await screen.findByText(/offline/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /welcome to recliniq/i })).toBeInTheDocument()
  })
})

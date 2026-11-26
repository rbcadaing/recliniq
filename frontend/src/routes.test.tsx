import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderAt } from './test/render'

describe('routing', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok', name: 'RecliniQ', version: '0.1.0' }), {
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  it('renders the home page at /', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { name: /welcome to recliniq/i })).toBeInTheDocument()
  })

  it('renders the not-found page with a link back home for unknown paths', async () => {
    renderAt('/no/such/page')
    expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: /back to home/i }))
    expect(await screen.findByRole('heading', { name: /welcome to recliniq/i })).toBeInTheDocument()
  })
})

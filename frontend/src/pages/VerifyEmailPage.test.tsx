import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, mockApi } from '../test/mockApi'
import { renderAt } from '../test/render'

const CONFIRM = 'POST /api/v1/auth/email-verification/confirm'
const RESEND = 'POST /api/v1/auth/email-verification/resend'

describe('VerifyEmailPage', () => {
  it('confirms the token exactly once (even in StrictMode) and shows success', async () => {
    const calls = mockApi({ [CONFIRM]: () => json({ message: 'Your email is verified.' }) })

    renderAt('/verify-email?token=abc123')

    expect(await screen.findByRole('heading', { name: /email verified/i })).toBeInTheDocument()
    expect(screen.getByText(/pending verification/i)).toBeInTheDocument()
    const confirms = calls.filter((c) => c.path.endsWith('/confirm'))
    expect(confirms).toEqual([
      {
        method: 'POST',
        path: '/api/v1/auth/email-verification/confirm',
        body: { token: 'abc123' },
      },
    ])
  })

  it('explains an expired link and lets the user request a new one', async () => {
    const calls = mockApi({
      [CONFIRM]: () => apiError(400, 'token_expired', 'This link has expired.'),
      [RESEND]: () =>
        json({ message: "If this email needs verifying, we've sent a new link." }, 202),
    })
    renderAt('/verify-email?token=old')

    expect(await screen.findByRole('heading', { name: /link has expired/i })).toBeInTheDocument()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'juan@example.com')
    await user.click(screen.getByRole('button', { name: /send a new verification email/i }))

    expect(await screen.findByText(/we've sent a new link/i)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/resend'))?.body).toEqual({
      email: 'juan@example.com',
    })
  })

  it('explains an invalid or used link', async () => {
    mockApi({
      [CONFIRM]: () =>
        apiError(400, 'invalid_token', 'This link is invalid or has already been used.'),
    })
    renderAt('/verify-email?token=used')

    expect(
      await screen.findByRole('heading', { name: /invalid or has already been used/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /send a new verification email/i }),
    ).toBeInTheDocument()
  })

  it('handles a link without a token without calling the API', () => {
    const calls = mockApi({})
    renderAt('/verify-email')

    expect(screen.getByRole('heading', { name: /link is incomplete/i })).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })
})

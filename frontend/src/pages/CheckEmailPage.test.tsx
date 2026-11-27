import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, mockApi } from '../test/mockApi'
import { renderAt } from '../test/render'

const RESEND = 'POST /api/v1/auth/email-verification/resend'

describe('CheckEmailPage', () => {
  it('shows the submitted email and resends to it', async () => {
    const calls = mockApi({
      [RESEND]: () =>
        json({ message: "If this email needs verifying, we've sent a new link." }, 202),
    })
    renderAt('/signup/check-email', { email: 'juan@example.com' })

    expect(screen.getByText('juan@example.com')).toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /send a new verification email/i }))

    expect(await screen.findByText(/we've sent a new link/i)).toBeInTheDocument()
    expect(calls[0]?.body).toEqual({ email: 'juan@example.com' })
  })

  it('shows a rate-limit message when resending too often', async () => {
    mockApi({
      [RESEND]: () =>
        apiError(429, 'too_many_requests', 'Too many attempts.', null, { 'Retry-After': '45' }),
    })
    renderAt('/signup/check-email', { email: 'juan@example.com' })

    await userEvent.click(screen.getByRole('button', { name: /send a new verification email/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/try again in 1 minute\./i)
  })

  it('asks for the email when opened directly', () => {
    mockApi({})
    renderAt('/signup/check-email')

    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })
})

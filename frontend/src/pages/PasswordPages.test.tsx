import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, mockApi } from '../test/mockApi'
import { renderAt } from '../test/render'
import { FORGOT_CONFIRMATION } from './ForgotPasswordPage'

const FORGOT = 'POST /api/v1/auth/password/forgot'
const RESET = 'POST /api/v1/auth/password/reset'
const NEW_PASSWORD = 'brand new passphrase'

describe('ForgotPasswordPage', () => {
  it('always shows the same confirmation', async () => {
    const calls = mockApi({ [FORGOT]: () => json({ message: 'whatever the server says' }, 202) })
    renderAt('/forgot-password')
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'juan@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByText(FORGOT_CONFIRMATION)).toBeInTheDocument()
    expect(calls[0]?.body).toEqual({ email: 'juan@example.com' })
  })

  it('shows a rate-limit message', async () => {
    mockApi({
      [FORGOT]: () =>
        apiError(429, 'too_many_requests', 'Too many attempts.', null, { 'Retry-After': '60' }),
    })
    renderAt('/forgot-password')
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'juan@example.com')
    await user.click(screen.getByRole('button', { name: /send reset link/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/try again in 1 minute\./i)
  })
})

async function choosePassword(password = NEW_PASSWORD, confirm = password) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('New password'), password)
  await user.type(screen.getByLabelText('Confirm new password'), confirm)
  await user.click(screen.getByRole('button', { name: /change password/i }))
}

describe('ResetPasswordPage', () => {
  it('resets the password and points to login', async () => {
    const calls = mockApi({ [RESET]: () => json({ message: 'ok' }) })
    renderAt('/reset-password?token=tok-123')

    await choosePassword()

    expect(await screen.findByRole('heading', { name: /password changed/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /log in with your new password/i })).toHaveAttribute(
      'href',
      '/login',
    )
    expect(calls[0]?.body).toEqual({ token: 'tok-123', new_password: NEW_PASSWORD })
  })

  it('checks length and confirmation before calling the backend', async () => {
    const calls = mockApi({})
    renderAt('/reset-password?token=tok-123')

    await choosePassword('short', 'different')

    expect(screen.getByText(/at least 12 characters/i, { selector: '.field__error' })).toBeVisible()
    expect(screen.getByText(/passwords don't match/i)).toBeVisible()
    expect(calls).toHaveLength(0)
  })

  it('shows the backend policy error on the password field', async () => {
    mockApi({
      [RESET]: () =>
        apiError(422, 'validation_error', 'The request is invalid.', [
          {
            field: 'body.new_password',
            message: 'Value error, is too common',
            type: 'value_error',
          },
        ]),
    })
    renderAt('/reset-password?token=tok-123')

    await choosePassword()

    expect(await screen.findByText('Is too common.')).toBeInTheDocument()
    expect(screen.getByLabelText('New password')).toHaveAttribute('aria-invalid', 'true')
  })

  it.each([
    ['token_expired', /link has expired/i],
    ['invalid_token', /invalid or has already been used/i],
  ])('explains a %s link and offers a new one', async (code, heading) => {
    mockApi({ [RESET]: () => apiError(400, code, 'nope') })
    renderAt('/reset-password?token=tok-123')

    await choosePassword()

    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /request a new reset link/i })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })

  it('keeps the token out of the Referer header', () => {
    mockApi({})
    renderAt('/reset-password?token=tok-123')

    expect(document.querySelector('meta[name="referrer"]')).toHaveAttribute(
      'content',
      'no-referrer',
    )
  })
})

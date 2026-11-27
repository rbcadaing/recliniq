import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { getAccessToken, getRefreshToken } from '../auth/session'
import { PENDING_DOCTOR } from '../test/fixtures'
import { apiError, json, mockApi } from '../test/mockApi'
import { renderAt } from '../test/render'

const LOGIN = 'POST /api/v1/auth/login'
const ME = 'GET /api/v1/me'
const REFRESH = 'POST /api/v1/auth/refresh'
const LOGOUT = 'POST /api/v1/auth/logout'

const TOKENS = {
  access_token: 'access-1',
  token_type: 'bearer',
  expires_in: 900,
  refresh_token: 'refresh-1',
  refresh_expires_in: 2592000,
}

async function submitLogin(email = 'juan@example.com', password = 'correct horse battery') {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: /^log in$/i }))
  return user
}

describe('LoginPage', () => {
  it('signs in, stores the session, and opens the account page', async () => {
    const calls = mockApi({ [LOGIN]: () => json(TOKENS), [ME]: () => json(PENDING_DOCTOR) })
    renderAt('/login')

    await submitLogin()

    expect(await screen.findByRole('heading', { name: /your account/i })).toBeInTheDocument()
    expect(screen.getByText('Pending verification')).toBeInTheDocument()
    expect(getAccessToken()).toBe('access-1')
    expect(getRefreshToken()).toBe('refresh-1')
    expect(calls.find((c) => c.path === '/api/v1/auth/login')?.body).toEqual({
      email: 'juan@example.com',
      password: 'correct horse battery',
    })
    // Header switched to the signed-in state.
    expect(screen.getByRole('link', { name: 'Juan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument()
  })

  it('shows a generic message for invalid credentials', async () => {
    mockApi({
      [LOGIN]: () => apiError(401, 'invalid_credentials', 'Incorrect email or password.'),
    })
    renderAt('/login')

    await submitLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(getRefreshToken()).toBeNull()
  })

  it('asks to verify the email and offers to resend to the typed address', async () => {
    const calls = mockApi({
      [LOGIN]: () => apiError(403, 'email_not_verified', 'Please verify your email address.'),
      'POST /api/v1/auth/email-verification/resend': () =>
        json({ message: "If this email needs verifying, we've sent a new link." }, 202),
    })
    renderAt('/login')
    const user = await submitLogin()

    expect(await screen.findByText(/verify your email address before signing in/i)).toBeVisible()
    await user.click(screen.getByRole('button', { name: /send a new verification email/i }))

    expect(await screen.findByText(/we've sent a new link/i)).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/resend'))?.body).toEqual({
      email: 'juan@example.com',
    })
  })

  it('tells the user how long to wait when rate limited', async () => {
    mockApi({
      [LOGIN]: () =>
        apiError(429, 'too_many_requests', 'Too many attempts.', null, { 'Retry-After': '300' }),
    })
    renderAt('/login')

    await submitLogin()

    expect(await screen.findByRole('alert')).toHaveTextContent(/try again in 5 minutes/i)
  })

  it('checks the fields before calling the backend', async () => {
    const calls = mockApi({})
    renderAt('/login')

    await userEvent.click(screen.getByRole('button', { name: /^log in$/i }))

    expect(screen.getByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(calls).toHaveLength(0)
  })

  it('links to forgot password and doctor sign-up', () => {
    mockApi({})
    renderAt('/login')

    expect(screen.getByRole('link', { name: /forgot your password/i })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
    expect(screen.getByRole('link', { name: /create an account/i })).toHaveAttribute(
      'href',
      '/signup/doctor',
    )
  })
})

describe('session lifecycle', () => {
  it('redirects a signed-out visitor from /account to login and back after signing in', async () => {
    mockApi({ [LOGIN]: () => json(TOKENS), [ME]: () => json(PENDING_DOCTOR) })
    const { router } = renderAt('/account')

    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
    await submitLogin()

    expect(await screen.findByRole('heading', { name: /your account/i })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/account')
  })

  it('restores the session from the stored refresh token on load', async () => {
    // As after a reload: a stored refresh token, no access token in memory.
    localStorage.setItem('recliniq.refreshToken', 'stored-refresh')
    const calls = mockApi({
      [REFRESH]: () => json({ ...TOKENS, access_token: 'access-2', refresh_token: 'refresh-2' }),
      [ME]: () => json(PENDING_DOCTOR),
    })

    renderAt('/account')

    expect(await screen.findByRole('heading', { name: /your account/i })).toBeInTheDocument()
    expect(calls.find((c) => c.path.endsWith('/refresh'))?.body).toEqual({
      refresh_token: 'stored-refresh',
    })
    expect(getRefreshToken()).toBe('refresh-2')
  })

  it('logs out: calls the backend, clears the session, and returns to login', async () => {
    const calls = mockApi({
      [LOGIN]: () => json(TOKENS),
      [ME]: () => json(PENDING_DOCTOR),
      [LOGOUT]: () => new Response(null, { status: 204 }),
    })
    renderAt('/login')
    const user = await submitLogin()
    await screen.findByRole('heading', { name: /your account/i })

    await user.click(screen.getByRole('button', { name: /log out/i }))

    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
    expect(getRefreshToken()).toBeNull()
    expect(getAccessToken()).toBeNull()
    expect(calls.find((c) => c.path.endsWith('/logout'))?.body).toEqual({
      refresh_token: 'refresh-1',
    })
    expect(screen.getByRole('link', { name: /^log in$/i })).toBeInTheDocument()
  })
})

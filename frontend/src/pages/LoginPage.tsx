import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'
import { fieldErrorsFrom, formErrorFrom } from '../features/accounts/apiErrors'
import { TextField } from '../features/accounts/FormField'
import { ResendVerification } from '../features/accounts/ResendVerification'
import { type FieldErrors, validateEmail, validateRequired } from '../features/accounts/validation'

function redirectTarget(state: unknown): string {
  if (state && typeof state === 'object' && 'from' in state && typeof state.from === 'string') {
    return state.from.startsWith('/') ? state.from : '/account'
  }
  return '/account'
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})

  const signIn = useMutation({
    mutationFn: (credentials: { email: string; password: string }) =>
      login(credentials.email, credentials.password),
    onSuccess: () => void navigate(redirectTarget(location.state), { replace: true }),
    onError: (error) => setErrors(fieldErrorsFrom(error)),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found: FieldErrors = {}
    const emailError = validateEmail(email)
    const passwordError = validateRequired(password, 'Enter your password.')
    if (emailError) found.email = emailError
    if (passwordError) found.password = passwordError
    setErrors(found)
    if (Object.keys(found).length === 0) signIn.mutate({ email: email.trim(), password })
  }

  const error = signIn.error
  const code = error instanceof ApiError ? error.code : undefined
  const formError =
    code === 'invalid_credentials'
      ? 'Incorrect email or password.'
      : code === 'email_not_verified'
        ? undefined
        : formErrorFrom(error)

  return (
    <section className="page page--narrow">
      <h1>Log in</h1>
      {/* Outside the login form: ResendVerification is a form of its own (no nesting). */}
      {code === 'email_not_verified' && (
        <div role="alert" className="banner banner--pending">
          <p>Please verify your email address before signing in. Check your inbox for the link.</p>
          <ResendVerification email={email.trim()} />
        </div>
      )}
      <form className="form" noValidate onSubmit={submit}>
        {formError && (
          <p role="alert" className="form__error">
            {formError}
          </p>
        )}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          error={errors.email}
          onChange={(e) => {
            setEmail(e.target.value)
            setErrors(({ email: _cleared, ...rest }) => rest)
          }}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          error={errors.password}
          onChange={(e) => {
            setPassword(e.target.value)
            setErrors(({ password: _cleared, ...rest }) => rest)
          }}
        />
        <button type="submit" className="button" disabled={signIn.isPending}>
          {signIn.isPending ? 'Signing in…' : 'Log in'}
        </button>
        <p className="page__muted">
          <Link to="/forgot-password">Forgot your password?</Link> · New doctor?{' '}
          <Link to="/signup/doctor">Create an account</Link>
        </p>
      </form>
    </section>
  )
}

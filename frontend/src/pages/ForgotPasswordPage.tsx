import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { forgotPassword } from '../api/auth'
import { formErrorFrom } from '../features/accounts/apiErrors'
import { TextField } from '../features/accounts/FormField'
import { validateEmail } from '../features/accounts/validation'

export const FORGOT_CONFIRMATION = "If an account exists for this email, we've sent a reset link."

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState<string>()
  const request = useMutation({ mutationFn: (address: string) => forgotPassword(address) })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const error = validateEmail(email)
    setEmailError(error)
    if (!error) request.mutate(email.trim())
  }

  if (request.isSuccess) {
    return (
      <section className="page page--narrow">
        <h1>Check your email</h1>
        {/* Same message whatever the outcome, so it can't reveal which emails are registered. */}
        <p>
          <output>{FORGOT_CONFIRMATION}</output>
        </p>
        <p className="page__muted">The link expires in 60 minutes.</p>
        <Link to="/login">Back to log in</Link>
      </section>
    )
  }

  const formError = formErrorFrom(request.error)
  return (
    <section className="page page--narrow">
      <h1>Reset your password</h1>
      <p className="page__lead">
        Enter your email and we&apos;ll send you a link to choose a new password.
      </p>
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
          error={emailError}
          onChange={(e) => {
            setEmail(e.target.value)
            setEmailError(undefined)
          }}
        />
        <button type="submit" className="button" disabled={request.isPending}>
          {request.isPending ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
    </section>
  )
}

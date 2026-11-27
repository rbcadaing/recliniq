import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'

import { resetPassword } from '../api/auth'
import { ApiError } from '../api/client'
import { fieldErrorsFrom, formErrorFrom } from '../features/accounts/apiErrors'
import { TextField } from '../features/accounts/FormField'
import { MIN_PASSWORD_LENGTH, validatePassword } from '../features/accounts/validation'

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({})

  const reset = useMutation({
    mutationFn: (newPassword: string) => resetPassword(token, newPassword),
    onError: (error) => {
      const fields = fieldErrorsFrom(error)
      if (fields.new_password) setErrors({ password: fields.new_password })
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = {
      password: validatePassword(password),
      confirm: password === confirm ? undefined : "The passwords don't match.",
    }
    setErrors(found)
    if (!found.password && !found.confirm) reset.mutate(password)
  }

  // The token is in the URL: don't leak it to other sites through the Referer header.
  const noReferrer = <meta name="referrer" content="no-referrer" />

  if (!token) return <LinkProblem title="This reset link is incomplete" meta={noReferrer} />
  if (reset.isSuccess) {
    return (
      <section className="page page--narrow">
        {noReferrer}
        <h1>Password changed</h1>
        <p>
          <output>
            Your password has been reset and you&apos;ve been signed out on all devices.
          </output>
        </p>
        <Link to="/login">Log in with your new password</Link>
      </section>
    )
  }
  const code = reset.error instanceof ApiError ? reset.error.code : undefined
  if (code === 'token_expired')
    return <LinkProblem title="This reset link has expired" meta={noReferrer} />
  if (code === 'invalid_token') {
    return (
      <LinkProblem title="This reset link is invalid or has already been used" meta={noReferrer} />
    )
  }

  const formError = code === 'validation_error' ? undefined : formErrorFrom(reset.error)
  return (
    <section className="page page--narrow">
      {noReferrer}
      <h1>Choose a new password</h1>
      <form className="form" noValidate onSubmit={submit}>
        {formError && (
          <p role="alert" className="form__error">
            {formError}
          </p>
        )}
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A few random words work well.`}
          value={password}
          error={errors.password}
          onChange={(e) => {
            setPassword(e.target.value)
            setErrors((current) => ({ ...current, password: undefined }))
          }}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          error={errors.confirm}
          onChange={(e) => {
            setConfirm(e.target.value)
            setErrors((current) => ({ ...current, confirm: undefined }))
          }}
        />
        <button type="submit" className="button" disabled={reset.isPending}>
          {reset.isPending ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </section>
  )
}

function LinkProblem({ title, meta }: { title: string; meta: ReactNode }) {
  return (
    <section className="page page--narrow">
      {meta}
      <h1>{title}</h1>
      <p>Reset links can be used once and expire after 60 minutes.</p>
      <Link to="/forgot-password">Request a new reset link</Link>
    </section>
  )
}

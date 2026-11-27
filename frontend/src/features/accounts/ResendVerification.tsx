import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { resendVerification } from '../../api/auth'
import { formErrorFrom } from './apiErrors'
import { TextField } from './FormField'
import { validateEmail } from './validation'

interface ResendVerificationProps {
  /** Known email (e.g. right after sign-up). Without it, the user types theirs. */
  email?: string
}

export function ResendVerification({ email: knownEmail }: ResendVerificationProps) {
  const [email, setEmail] = useState(knownEmail ?? '')
  const [emailError, setEmailError] = useState<string>()
  const resend = useMutation({ mutationFn: (address: string) => resendVerification(address) })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const error = validateEmail(email)
    setEmailError(error)
    if (!error) resend.mutate(email.trim())
  }

  const error = formErrorFrom(resend.error)

  return (
    <form className="form form--inline" noValidate onSubmit={submit}>
      {!knownEmail && (
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
      )}
      <button type="submit" className="button button--secondary" disabled={resend.isPending}>
        {resend.isPending ? 'Sending…' : 'Send a new verification email'}
      </button>
      <div aria-live="polite">
        {resend.isSuccess && <p className="form__success">{resend.data.message}</p>}
        {error && (
          <p role="alert" className="form__error">
            {error}
          </p>
        )}
      </div>
    </form>
  )
}

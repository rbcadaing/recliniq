import { useLocation } from 'react-router'

import { ResendVerification } from '../features/accounts/ResendVerification'

function emailFromState(state: unknown): string | undefined {
  if (state && typeof state === 'object' && 'email' in state && typeof state.email === 'string') {
    return state.email
  }
  return undefined
}

export function CheckEmailPage() {
  const email = emailFromState(useLocation().state)

  return (
    <section className="page page--narrow">
      <h1>Check your inbox</h1>
      <p>
        We sent a verification link to{' '}
        {email ? <strong>{email}</strong> : 'the email address you signed up with'}. Open it to
        activate your account. The link expires in 24 hours.
      </p>
      <p className="page__muted">Didn&apos;t get it? Check your spam folder, or send a new one.</p>
      <ResendVerification email={email} />
    </section>
  )
}

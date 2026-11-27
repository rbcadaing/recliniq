import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'

import { confirmEmail } from '../api/auth'
import { ApiError } from '../api/client'
import { ResendVerification } from '../features/accounts/ResendVerification'

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const confirm = useMutation({ mutationFn: (value: string) => confirmEmail(value) })
  const sent = useRef(false)

  useEffect(() => {
    // The token is single-use: confirm it exactly once, even when StrictMode re-runs effects.
    if (!token || sent.current) return
    sent.current = true
    confirm.mutate(token)
  }, [token, confirm])

  if (!token) return <LinkProblem title="This link is incomplete" />
  if (confirm.isSuccess) {
    return (
      <section className="page page--narrow">
        <h1>Email verified</h1>
        <p>
          Thanks! Your email is verified. Our team will review your PRC license; until then your
          account shows as <strong>Pending verification</strong>.
        </p>
        <Link to="/login">Sign in</Link>
      </section>
    )
  }
  if (confirm.isError) {
    const error = confirm.error
    if (error instanceof ApiError && error.code === 'token_expired') {
      return <LinkProblem title="This link has expired" />
    }
    if (error instanceof ApiError && error.code === 'invalid_token') {
      return <LinkProblem title="This link is invalid or has already been used" />
    }
    return (
      <section className="page page--narrow">
        <h1>We couldn&apos;t verify your email</h1>
        <p role="alert">{error.message}</p>
        <button type="button" className="button" onClick={() => confirm.mutate(token)}>
          Try again
        </button>
      </section>
    )
  }
  return (
    <section className="page page--narrow">
      <h1>Verifying your email…</h1>
    </section>
  )
}

function LinkProblem({ title }: { title: string }) {
  return (
    <section className="page page--narrow">
      <h1>{title}</h1>
      <p>
        If you already verified your email, you&apos;re all set. Otherwise, request a new link
        below.
      </p>
      <ResendVerification />
    </section>
  )
}

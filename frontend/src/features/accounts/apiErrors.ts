import { ApiError } from '../../api/client'
import type { FieldErrors } from './validation'

interface FieldDetail {
  field?: unknown
  message?: unknown
}

/** Last segment of a backend field name: `body.mobile` -> `mobile`. */
function fieldName(field: unknown): string | undefined {
  return typeof field === 'string' ? field.split('.').at(-1) : undefined
}

function cleanMessage(message: unknown): string | undefined {
  if (typeof message !== 'string' || !message) return undefined
  const text = message.replace(/^Value error, /, '')
  const sentence = text.charAt(0).toUpperCase() + text.slice(1)
  return sentence.endsWith('.') ? sentence : `${sentence}.`
}

/**
 * Map backend errors onto form fields:
 * - 422 `details: [{field, message}]` (request validation and service checks)
 * - 409 `details: {field}` (value already registered)
 */
export function fieldErrorsFrom(error: unknown): FieldErrors {
  if (!(error instanceof ApiError)) return {}
  const { details } = error
  if (Array.isArray(details)) {
    const errors: FieldErrors = {}
    for (const item of details as FieldDetail[]) {
      const name = fieldName(item.field)
      const message = cleanMessage(item.message)
      if (name && message && !errors[name]) errors[name] = message
    }
    return errors
  }
  if (error.status === 409 && details && typeof details === 'object' && 'field' in details) {
    const name = fieldName((details as FieldDetail).field)
    if (name) return { [name]: error.message }
  }
  return {}
}

/** A message for errors that don't belong to a single field. */
export function formErrorFrom(error: unknown): string | undefined {
  if (!error) return undefined
  if (!(error instanceof ApiError)) return 'Something went wrong. Please try again.'
  if (error.status === 429) {
    if (error.retryAfter === undefined) return 'Too many attempts. Please try again later.'
    const minutes = Math.max(1, Math.ceil(error.retryAfter / 60))
    return `Too many attempts. Please try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
  }
  if (error.kind === 'network') return error.message
  if (error.status === 422 || error.status === 409) return undefined
  return 'Something went wrong. Please try again.'
}

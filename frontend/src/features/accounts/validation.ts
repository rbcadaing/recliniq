/**
 * Client-side checks that mirror the backend rules (backend/app/domain/accounts). They give fast
 * feedback; the backend stays the authority (e.g. the common-password list is checked there).
 */

export const MIN_PASSWORD_LENGTH = 12
export const MAX_PASSWORD_LENGTH = 128

const PH_MOBILE = /^(?:\+?63|0)9\d{9}$/
const PRC_LICENSE = /^\d{1,7}$/
// Deliberately loose: one @, something on each side, a dot in the domain, no spaces.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export type FieldErrors = Partial<Record<string, string>>

export function validateEmail(value: string): string | undefined {
  const email = value.trim()
  if (!email) return 'Enter your email address.'
  if (email.length > 254 || !EMAIL.test(email)) return 'Enter a valid email address.'
  return undefined
}

export function validateMobile(value: string): string | undefined {
  const mobile = value.trim().replace(/[\s-]/g, '')
  if (!mobile) return 'Enter your mobile number.'
  if (!PH_MOBILE.test(mobile)) return 'Enter a Philippine mobile number, e.g. 0917 123 4567.'
  return undefined
}

export function validatePrcLicense(value: string): string | undefined {
  const prc = value.trim()
  if (!prc) return 'Enter your PRC license number.'
  if (!PRC_LICENSE.test(prc)) return 'PRC license numbers are 1 to 7 digits.'
  return undefined
}

export function validatePassword(value: string, email?: string): string | undefined {
  const length = [...value.normalize('NFKC')].length
  if (length < MIN_PASSWORD_LENGTH) return `Use at least ${MIN_PASSWORD_LENGTH} characters.`
  if (length > MAX_PASSWORD_LENGTH) return `Use at most ${MAX_PASSWORD_LENGTH} characters.`
  if (email && value.trim().toLowerCase() === email.trim().toLowerCase()) {
    return "Your password can't be your email address."
  }
  return undefined
}

export function validateRequired(value: string, message: string): string | undefined {
  return value.trim() ? undefined : message
}

export interface DoctorSignUpForm {
  firstName: string
  middleName: string
  lastName: string
  email: string
  mobile: string
  password: string
  specializationId: string
  prcLicenseNo: string
  privacyConsent: boolean
}

/** Errors keyed by the backend's field names, so backend and client errors share one map. */
export function validateDoctorSignUp(form: DoctorSignUpForm): FieldErrors {
  const errors: FieldErrors = {
    first_name: validateRequired(form.firstName, 'Enter your first name.'),
    last_name: validateRequired(form.lastName, 'Enter your last name.'),
    email: validateEmail(form.email),
    mobile: validateMobile(form.mobile),
    password: validatePassword(form.password, form.email),
    specialization_id: validateRequired(form.specializationId, 'Choose your specialization.'),
    prc_license_no: validatePrcLicense(form.prcLicenseNo),
    privacy_consent: form.privacyConsent ? undefined : 'You must accept the privacy notice.',
  }
  return Object.fromEntries(Object.entries(errors).filter(([, message]) => message))
}

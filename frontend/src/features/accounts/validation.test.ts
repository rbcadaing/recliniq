import { describe, expect, it } from 'vitest'

import { ApiError } from '../../api/client'
import { fieldErrorsFrom, formErrorFrom } from './apiErrors'
import {
  type DoctorSignUpForm,
  validateDoctorSignUp,
  validateEmail,
  validateMobile,
  validatePassword,
  validatePrcLicense,
} from './validation'

describe('account validators (mirror the backend examples)', () => {
  it.each(['0917 123 4567', '09171234567', '639171234567', '+639171234567', '+63-917-123-4567'])(
    'accepts PH mobile %s',
    (mobile) => expect(validateMobile(mobile)).toBeUndefined(),
  )

  it.each(['+14155550100', '0917123', '08171234567', ''])('rejects mobile %j', (mobile) =>
    expect(validateMobile(mobile)).toBeDefined(),
  )

  it.each(['12345', '0012345', '1234567', ' 1 '])('accepts PRC %j', (prc) =>
    expect(validatePrcLicense(prc)).toBeUndefined(),
  )

  it.each(['AB12345', '12345678', '', '12 345'])('rejects PRC %j', (prc) =>
    expect(validatePrcLicense(prc)).toBeDefined(),
  )

  it('checks email shape', () => {
    expect(validateEmail('Juan.DelaCruz@Example.COM')).toBeUndefined()
    expect(validateEmail('not-an-email')).toBeDefined()
    expect(validateEmail(`${'a'.repeat(250)}@example.com`)).toBeDefined()
  })

  it('checks password length and email reuse, not composition', () => {
    expect(validatePassword('a'.repeat(11))).toMatch(/at least 12/)
    expect(validatePassword('a'.repeat(129))).toMatch(/at most 128/)
    expect(validatePassword('correct horse battery staple')).toBeUndefined()
    expect(validatePassword('doc.juan@example.com', 'Doc.Juan@example.com')).toMatch(/email/)
  })

  it('reports every invalid field of the sign-up form by backend field name', () => {
    const empty: DoctorSignUpForm = {
      firstName: '',
      middleName: '',
      lastName: '',
      email: '',
      mobile: '',
      password: '',
      specializationId: '',
      prcLicenseNo: '',
      privacyConsent: false,
    }
    expect(Object.keys(validateDoctorSignUp(empty)).sort()).toEqual([
      'email',
      'first_name',
      'last_name',
      'mobile',
      'password',
      'prc_license_no',
      'privacy_consent',
      'specialization_id',
    ])
  })
})

describe('backend errors', () => {
  it('maps 422 details to fields by their last segment', () => {
    const error = new ApiError({
      kind: 'http',
      status: 422,
      code: 'validation_error',
      message: 'The request is invalid.',
      details: [
        {
          field: 'body.password',
          message: 'Value error, is too common; choose a less predictable password',
        },
        { field: 'specialization_id', message: 'Unknown specialization.' },
      ],
    })
    expect(fieldErrorsFrom(error)).toEqual({
      password: 'Is too common; choose a less predictable password.',
      specialization_id: 'Unknown specialization.',
    })
    expect(formErrorFrom(error)).toBeUndefined()
  })

  it('maps a 409 conflict to its field', () => {
    const error = new ApiError({
      kind: 'http',
      status: 409,
      code: 'conflict',
      message: 'This mobile is already registered.',
      details: { field: 'mobile' },
    })
    expect(fieldErrorsFrom(error)).toEqual({ mobile: 'This mobile is already registered.' })
  })

  it('turns 429 Retry-After into minutes', () => {
    const error = new ApiError({
      kind: 'http',
      status: 429,
      code: 'too_many_requests',
      message: 'Too many attempts.',
      retryAfter: 125,
    })
    expect(formErrorFrom(error)).toBe('Too many attempts. Please try again in 3 minutes.')
  })
})

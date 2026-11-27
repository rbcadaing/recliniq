import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { type DoctorSignUpRequest, signUpDoctor } from '../api/auth'
import { getSpecializations } from '../api/specializations'
import { fieldErrorsFrom, formErrorFrom } from '../features/accounts/apiErrors'
import { Field, TextField } from '../features/accounts/FormField'
import {
  type DoctorSignUpForm,
  type FieldErrors,
  MIN_PASSWORD_LENGTH,
  validateDoctorSignUp,
} from '../features/accounts/validation'

const EMPTY_FORM: DoctorSignUpForm = {
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

// Form keys -> backend field names (errors are keyed by the backend names).
const FIELD_NAMES: Record<keyof DoctorSignUpForm, string> = {
  firstName: 'first_name',
  middleName: 'middle_name',
  lastName: 'last_name',
  email: 'email',
  mobile: 'mobile',
  password: 'password',
  specializationId: 'specialization_id',
  prcLicenseNo: 'prc_license_no',
  privacyConsent: 'privacy_consent',
}

export function DoctorSignUpPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<DoctorSignUpForm>(EMPTY_FORM)
  const [errors, setErrors] = useState<FieldErrors>({})
  const formRef = useRef<HTMLFormElement>(null)
  // Bumped on every rejected submit; focus moves to the first invalid field after rendering.
  const [failedSubmits, setFailedSubmits] = useState(0)

  useEffect(() => {
    if (failedSubmits > 0) {
      formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus()
    }
  }, [failedSubmits])
  const specializations = useQuery({
    queryKey: ['specializations'],
    queryFn: () => getSpecializations(),
    staleTime: Infinity,
  })

  const signUp = useMutation({
    mutationFn: (request: DoctorSignUpRequest) => signUpDoctor(request),
    onSuccess: (_, request) => {
      void navigate('/signup/check-email', { state: { email: request.email } })
    },
    onError: (error) => {
      setErrors(fieldErrorsFrom(error))
      setFailedSubmits((n) => n + 1)
    },
  })

  function update<K extends keyof DoctorSignUpForm>(key: K, value: DoctorSignUpForm[K]) {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors(({ [FIELD_NAMES[key]]: _cleared, ...rest }) => rest)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateDoctorSignUp(form)
    setErrors(found)
    if (Object.keys(found).length > 0) {
      setFailedSubmits((n) => n + 1)
      return
    }
    signUp.mutate({
      first_name: form.firstName.trim(),
      middle_name: form.middleName.trim() || null,
      last_name: form.lastName.trim(),
      email: form.email.trim(),
      mobile: form.mobile.trim(),
      password: form.password,
      specialization_id: form.specializationId,
      prc_license_no: form.prcLicenseNo.trim(),
      privacy_consent: form.privacyConsent,
    })
  }

  const formError = formErrorFrom(signUp.error)

  return (
    <section className="page page--narrow">
      <h1>Create your doctor account</h1>
      <p className="page__lead">
        After you verify your email, our team reviews your PRC license before you can publish
        schedules.
      </p>

      <form ref={formRef} className="form" noValidate onSubmit={submit}>
        {formError && (
          <p role="alert" className="form__error">
            {formError}
          </p>
        )}

        <div className="form__row">
          <TextField
            label="First name"
            autoComplete="given-name"
            value={form.firstName}
            error={errors.first_name}
            onChange={(e) => update('firstName', e.target.value)}
          />
          <TextField
            label="Middle name (optional)"
            autoComplete="additional-name"
            value={form.middleName}
            error={errors.middle_name}
            onChange={(e) => update('middleName', e.target.value)}
          />
        </div>
        <TextField
          label="Last name"
          autoComplete="family-name"
          value={form.lastName}
          error={errors.last_name}
          onChange={(e) => update('lastName', e.target.value)}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={form.email}
          error={errors.email}
          onChange={(e) => update('email', e.target.value)}
        />
        <TextField
          label="Mobile number"
          type="tel"
          autoComplete="tel"
          inputMode="tel"
          placeholder="0917 123 4567"
          value={form.mobile}
          error={errors.mobile}
          onChange={(e) => update('mobile', e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters. A few random words work well.`}
          value={form.password}
          error={errors.password}
          onChange={(e) => update('password', e.target.value)}
        />
        <Field label="Specialization" error={errors.specialization_id}>
          {(a11y) => (
            <select
              className="field__input"
              {...a11y}
              value={form.specializationId}
              disabled={!specializations.isSuccess}
              onChange={(e) => update('specializationId', e.target.value)}
            >
              <option value="">
                {specializations.isPending
                  ? 'Loading…'
                  : specializations.isError
                    ? 'Could not load specializations'
                    : 'Choose…'}
              </option>
              {specializations.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <TextField
          label="PRC license number"
          inputMode="numeric"
          hint="Up to 7 digits, as shown on your PRC ID."
          value={form.prcLicenseNo}
          error={errors.prc_license_no}
          onChange={(e) => update('prcLicenseNo', e.target.value)}
        />

        <div className="field">
          <label className="field__checkbox">
            <input
              type="checkbox"
              checked={form.privacyConsent}
              aria-invalid={Boolean(errors.privacy_consent)}
              onChange={(e) => update('privacyConsent', e.target.checked)}
            />
            <span>
              I have read and accept the{' '}
              <Link to="/privacy" target="_blank" rel="noopener">
                privacy notice
              </Link>
              , and I consent to RecliniQ processing my personal information.
            </span>
          </label>
          {errors.privacy_consent && <p className="field__error">{errors.privacy_consent}</p>}
        </div>

        <button type="submit" className="button" disabled={signUp.isPending}>
          {signUp.isPending ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </section>
  )
}

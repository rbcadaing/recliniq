import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { apiError, json, mockApi, SPECIALIZATIONS } from '../test/mockApi'
import { renderAt } from '../test/render'

const SIGNUP = 'POST /api/v1/auth/doctors/signup'
const LIST = 'GET /api/v1/specializations'

async function fillValidForm() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('First name'), 'Juan')
  await user.type(screen.getByLabelText('Last name'), 'Dela Cruz')
  await user.type(screen.getByLabelText('Email'), 'juan@example.com')
  await user.type(screen.getByLabelText('Mobile number'), '0917 123 4567')
  await user.type(screen.getByLabelText('Password'), 'correct horse battery staple')
  await user.selectOptions(await screen.findByLabelText('Specialization'), 'Pediatrics')
  await user.type(screen.getByLabelText('PRC license number'), '12345')
  await user.click(screen.getByRole('checkbox', { name: /privacy notice/i }))
  return user
}

function errorFor(label: string) {
  const input = screen.getByLabelText(label)
  const describedBy = input.getAttribute('aria-describedby') ?? ''
  return describedBy
    .split(' ')
    .map((id) => document.getElementById(id)?.textContent)
    .join(' ')
}

describe('DoctorSignUpPage', () => {
  it('shows client-side errors and does not submit an invalid form', async () => {
    const calls = mockApi({ [LIST]: () => json(SPECIALIZATIONS) })
    renderAt('/signup/doctor')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Mobile number'), '0917123')
    await user.type(screen.getByLabelText('Password'), 'short')

    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(screen.getByLabelText('First name')).toHaveAttribute('aria-invalid', 'true')
    expect(errorFor('Mobile number')).toMatch(/Philippine mobile number/)
    expect(errorFor('Password')).toMatch(/at least 12/)
    expect(screen.getByText(/must accept the privacy notice/i)).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(0)
    expect(screen.getByLabelText('First name')).toHaveFocus()
  })

  it('sends the form and moves to the check-email page on success', async () => {
    const calls = mockApi({
      [LIST]: () => json(SPECIALIZATIONS),
      [SIGNUP]: () => json({ message: 'Check your email.' }, 202),
    })
    renderAt('/signup/doctor')
    const user = await fillValidForm()

    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByRole('heading', { name: /check your inbox/i })).toBeInTheDocument()
    expect(screen.getByText('juan@example.com')).toBeInTheDocument()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      first_name: 'Juan',
      middle_name: null,
      last_name: 'Dela Cruz',
      email: 'juan@example.com',
      mobile: '0917 123 4567',
      password: 'correct horse battery staple',
      specialization_id: SPECIALIZATIONS[1]!.id,
      prc_license_no: '12345',
      privacy_consent: true,
    })
  })

  it('shows a backend field error next to its field and keeps the entered values', async () => {
    mockApi({
      [LIST]: () => json(SPECIALIZATIONS),
      [SIGNUP]: () =>
        apiError(409, 'conflict', 'This mobile is already registered.', { field: 'mobile' }),
    })
    renderAt('/signup/doctor')
    const user = await fillValidForm()

    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('This mobile is already registered.')).toBeInTheDocument()
    expect(screen.getByLabelText('Mobile number')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('First name')).toHaveValue('Juan')
    expect(screen.getByLabelText('Email')).toHaveValue('juan@example.com')
    expect(screen.getByLabelText('PRC license number')).toHaveValue('12345')
  })

  it('maps 422 field details from the backend', async () => {
    mockApi({
      [LIST]: () => json(SPECIALIZATIONS),
      [SIGNUP]: () =>
        apiError(422, 'validation_error', 'The request is invalid.', [
          { field: 'body.password', message: 'Value error, is too common', type: 'value_error' },
        ]),
    })
    renderAt('/signup/doctor')
    const user = await fillValidForm()

    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText('Is too common.')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('aria-invalid', 'true')
  })

  it('explains when there were too many attempts', async () => {
    mockApi({
      [LIST]: () => json(SPECIALIZATIONS),
      [SIGNUP]: () =>
        apiError(429, 'too_many_requests', 'Too many attempts.', null, { 'Retry-After': '600' }),
    })
    renderAt('/signup/doctor')
    const user = await fillValidForm()

    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/try again in 10 minutes/i)
  })

  it('lists specializations and links to the privacy notice', async () => {
    mockApi({ [LIST]: () => json(SPECIALIZATIONS) })
    renderAt('/signup/doctor')

    const select = await screen.findByLabelText('Specialization')
    expect(await within(select).findByRole('option', { name: 'Cardiology' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /privacy notice/i })).toHaveAttribute(
      'href',
      '/privacy',
    )
  })
})

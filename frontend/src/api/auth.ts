import { api, type ApiClient } from './client'

export interface DoctorSignUpRequest {
  first_name: string
  middle_name: string | null
  last_name: string
  email: string
  mobile: string
  password: string
  specialization_id: string
  prc_license_no: string
  privacy_consent: boolean
}

export interface MessageResponse {
  message: string
}

export function signUpDoctor(
  request: DoctorSignUpRequest,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/doctors/signup', request)
}

export function confirmEmail(token: string, client: ApiClient = api): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/email-verification/confirm', { token })
}

export function resendVerification(
  email: string,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/email-verification/resend', { email })
}

// --- Sessions (US-01.3) ---------------------------------------------------------------------

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  refresh_token: string
  refresh_expires_in: number
}

export type Role = 'doctor' | 'patient' | 'staff' | 'admin'
export type LicenseStatus = 'pending' | 'approved' | 'rejected'

export interface AccountProfile {
  id: string
  first_name: string
  middle_name: string | null
  last_name: string
  email: string
  role: Role
  email_verified: boolean
  doctor: { specialization: { id: string; name: string }; license_status: LicenseStatus } | null
}

export function login(
  email: string,
  password: string,
  client: ApiClient = api,
): Promise<TokenResponse> {
  return client.post<TokenResponse>('/api/v1/auth/login', { email, password })
}

export function logout(refreshToken: string, client: ApiClient = api): Promise<void> {
  return client.post<void>('/api/v1/auth/logout', { refresh_token: refreshToken })
}

export function forgotPassword(email: string, client: ApiClient = api): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/password/forgot', { email })
}

export function resetPassword(
  token: string,
  newPassword: string,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/password/reset', {
    token,
    new_password: newPassword,
  })
}

export function getMe(client: ApiClient = api): Promise<AccountProfile> {
  return client.get<AccountProfile>('/api/v1/me')
}

import { api, type ApiClient } from './client'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export type DoctorSignUpRequest = Schemas['DoctorSignUpRequest']
export type MessageResponse = Schemas['MessageResponse']

export function signUpDoctor(
  request: DoctorSignUpRequest,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/doctors/signup', request)
}

export function confirmEmail(token: string, client: ApiClient = api): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/email-verification/confirm', {
    token,
  } satisfies Schemas['ConfirmRequest'])
}

export function resendVerification(
  email: string,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/email-verification/resend', {
    email,
  } satisfies Schemas['ResendRequest'])
}

// --- Sessions (US-01.3) ---------------------------------------------------------------------

export type TokenResponse = Schemas['TokenResponse']
export type Role = Schemas['Role']
export type LicenseStatus = Schemas['LicenseStatus']
export type AccountProfile = Schemas['AccountProfileResponse']

export function login(
  email: string,
  password: string,
  client: ApiClient = api,
): Promise<TokenResponse> {
  return client.post<TokenResponse>('/api/v1/auth/login', {
    email,
    password,
  } satisfies Schemas['LoginRequest'])
}

export function logout(refreshToken: string, client: ApiClient = api): Promise<void> {
  return client.post<void>('/api/v1/auth/logout', {
    refresh_token: refreshToken,
  } satisfies Schemas['RefreshRequest'])
}

export function forgotPassword(email: string, client: ApiClient = api): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/password/forgot', {
    email,
  } satisfies Schemas['ResendRequest'])
}

export function resetPassword(
  token: string,
  newPassword: string,
  client: ApiClient = api,
): Promise<MessageResponse> {
  return client.post<MessageResponse>('/api/v1/auth/password/reset', {
    token,
    new_password: newPassword,
  } satisfies Schemas['ResetPasswordRequest'])
}

export function getMe(client: ApiClient = api): Promise<AccountProfile> {
  return client.get<AccountProfile>('/api/v1/me')
}

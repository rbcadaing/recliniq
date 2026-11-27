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

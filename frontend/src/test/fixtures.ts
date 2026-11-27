import type { AccountProfile } from '../api/auth'

export const PENDING_DOCTOR: AccountProfile = {
  id: 'u1',
  first_name: 'Juan',
  middle_name: null,
  last_name: 'Dela Cruz',
  email: 'juan@example.com',
  role: 'doctor',
  email_verified: true,
  doctor: { specialization: { id: 's1', name: 'Pediatrics' }, license_status: 'pending' },
}

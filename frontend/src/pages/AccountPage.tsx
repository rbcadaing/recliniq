import type { AccountProfile, LicenseStatus, Role } from '../api/auth'
import { useAuth } from '../auth/context'

const ROLE_LABELS: Record<Role, string> = {
  doctor: 'Doctor',
  patient: 'Patient',
  staff: 'Clinic staff',
  admin: 'Administrator',
}

const LICENSE: Record<LicenseStatus, { label: string; explanation: string }> = {
  pending: {
    label: 'Pending verification',
    explanation:
      'Our team is reviewing your PRC license. You can sign in and set up your profile, but you ' +
      "can't publish schedules until your license is approved.",
  },
  rejected: {
    label: 'License not approved',
    explanation:
      "We couldn't verify your PRC license. Check the email we sent you for the reason and how " +
      'to resubmit.',
  },
  approved: {
    label: 'Verified',
    explanation: 'Your PRC license is verified. You can publish schedules and accept bookings.',
  },
}

function fullName(user: AccountProfile): string {
  return [user.first_name, user.middle_name, user.last_name].filter(Boolean).join(' ')
}

/** Rendered behind <RequireAuth>, so a signed-in user is always present. */
export function AccountPage() {
  const { user } = useAuth()
  if (!user) return null
  const license = user.doctor ? LICENSE[user.doctor.license_status] : undefined

  return (
    <section className="page page--narrow">
      <h1>Your account</h1>
      {license && user.doctor && (
        <div className={`banner banner--${user.doctor.license_status}`}>
          <strong>{license.label}</strong>
          <p>{license.explanation}</p>
        </div>
      )}
      <dl className="details">
        <dt>Name</dt>
        <dd>{fullName(user)}</dd>
        <dt>Email</dt>
        <dd>{user.email}</dd>
        <dt>Role</dt>
        <dd>{ROLE_LABELS[user.role]}</dd>
        {user.doctor && (
          <>
            <dt>Specialization</dt>
            <dd>{user.doctor.specialization.name}</dd>
          </>
        )}
      </dl>
    </section>
  )
}

import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { setSession } from '../auth/session'
import { json, mockApi } from '../test/mockApi'
import { renderAt } from '../test/render'
import { PENDING_DOCTOR } from '../test/fixtures'

function signedInAs(profile: unknown) {
  setSession({ access_token: 'access-1', refresh_token: 'refresh-1' })
  return mockApi({ 'GET /api/v1/me': () => json(profile) })
}

describe('AccountPage', () => {
  it.each([
    ['pending', 'Pending verification', /reviewing your PRC license/i],
    ['rejected', 'License not approved', /couldn't verify your PRC license/i],
    ['approved', 'Verified', /can publish schedules/i],
  ])('shows the %s license banner', async (status, label, explanation) => {
    signedInAs({
      ...PENDING_DOCTOR,
      doctor: { ...PENDING_DOCTOR.doctor!, license_status: status },
    })

    renderAt('/account')

    expect(await screen.findByText(label)).toBeInTheDocument()
    expect(screen.getByText(explanation)).toBeInTheDocument()
    expect(screen.getByText('Pediatrics')).toBeInTheDocument()
    expect(screen.getByText('juan@example.com')).toBeInTheDocument()
  })

  it('sends the access token when loading the profile', async () => {
    const calls = signedInAs(PENDING_DOCTOR)
    renderAt('/account')

    await screen.findByRole('heading', { name: /your account/i })

    expect(calls.find((c) => c.path === '/api/v1/me')).toBeDefined()
    const meRequest = (
      globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } }
    ).mock.calls.find(([url]) => String(url).endsWith('/api/v1/me'))
    expect(new Headers(meRequest?.[1].headers).get('Authorization')).toBe('Bearer access-1')
  })
})

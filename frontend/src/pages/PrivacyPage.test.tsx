import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderAt } from '../test/render'
import { PRIVACY_NOTICE_VERSION } from './PrivacyPage'

describe('PrivacyPage', () => {
  it('shows the placeholder notice with its version', () => {
    renderAt('/privacy')

    expect(screen.getByRole('heading', { name: /privacy notice/i })).toBeInTheDocument()
    expect(screen.getByText(new RegExp(PRIVACY_NOTICE_VERSION))).toBeInTheDocument()
  })
})

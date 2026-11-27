import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

import { resetSessionForTests } from '../auth/session'

afterEach(() => {
  cleanup()
  resetSessionForTests()
})

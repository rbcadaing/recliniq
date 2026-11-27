import type { RouteObject } from 'react-router'

import { Layout } from './components/Layout'
import { CheckEmailPage } from './pages/CheckEmailPage'
import { DoctorSignUpPage } from './pages/DoctorSignUpPage'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'signup/doctor', element: <DoctorSignUpPage /> },
      { path: 'signup/check-email', element: <CheckEmailPage /> },
      { path: 'verify-email', element: <VerifyEmailPage /> },
      { path: 'privacy', element: <PrivacyPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

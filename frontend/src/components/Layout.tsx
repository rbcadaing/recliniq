import { Link, Outlet, useNavigate } from 'react-router'

import { useAuth } from '../auth/context'

export function Layout() {
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()

  async function signOut() {
    await logout()
    void navigate('/login')
  }

  return (
    <div className="layout">
      <header className="layout__header">
        <Link to="/" className="layout__brand">
          RecliniQ
        </Link>
        <nav className="layout__nav" aria-label="Main">
          {status === 'signedIn' && user ? (
            <>
              <Link to="/account">{user.first_name}</Link>
              <button type="button" className="link-button" onClick={() => void signOut()}>
                Log out
              </button>
            </>
          ) : (
            status === 'signedOut' && (
              <>
                <Link to="/login">Log in</Link>
                <Link to="/signup/doctor">Sign up as a doctor</Link>
              </>
            )
          )}
        </nav>
      </header>
      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}

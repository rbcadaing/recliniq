import { Link, Outlet } from 'react-router'

export function Layout() {
  return (
    <div className="layout">
      <header className="layout__header">
        <Link to="/" className="layout__brand">
          RecliniQ
        </Link>
        <nav className="layout__nav" aria-label="Main">
          <Link to="/signup/doctor">Sign up as a doctor</Link>
        </nav>
      </header>
      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}

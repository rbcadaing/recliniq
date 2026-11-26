import { Link, Outlet } from 'react-router'

export function Layout() {
  return (
    <div className="layout">
      <header className="layout__header">
        <Link to="/" className="layout__brand">
          RecliniQ
        </Link>
      </header>
      <main className="layout__main">
        <Outlet />
      </main>
    </div>
  )
}

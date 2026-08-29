import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, setToken, type User } from "./api";
import SiteFooter from "./portal/SiteFooter";
import SiteHeader from "./portal/SiteHeader";

export default function Shell() {
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {
        setToken(null);
        const next = `${location.pathname}${location.search}`;
        navigate(`/login?next=${encodeURIComponent(next)}`);
      });
  }, [location.pathname, location.search, navigate]);

  if (!user) return <div className="page-loader">Loading your clinic…</div>;
  const staff = user.role === "doctor" || user.role === "assistant";

  return (
    <div className="site">
      <SiteHeader user={user} />
      <main className="app-shell">
        <aside className="app-sidebar">
          <span className="eyebrow">My clinic</span>
          <nav className="app-nav" aria-label="Clinic">
            <NavLink end to="/app">Home</NavLink>
            {!staff && <NavLink to="/app/book">Book consultation</NavLink>}
            <NavLink to="/app/history">Visit history</NavLink>
            <NavLink to="/app/alerts">Alerts</NavLink>
            {staff && <NavLink to="/app/schedule">Schedule</NavLink>}
            {staff && <NavLink to="/app/on-behalf">Book for patient</NavLink>}
          </nav>
        </aside>
        <div className="app-content">
          <Outlet context={user} />
        </div>
      </main>
      <SiteFooter user={user} />
    </div>
  );
}

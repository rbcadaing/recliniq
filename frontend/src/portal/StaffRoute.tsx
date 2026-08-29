import { Link, Outlet, useOutletContext } from "react-router-dom";
import type { User } from "../api";

export default function StaffRoute() {
  const user = useOutletContext<User>();
  const isStaff = user.role === "doctor" || user.role === "assistant";

  if (!isStaff) {
    return (
      <section className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">
          ⊘
        </span>
        <h1>Staff access only</h1>
        <p>Clinic schedules and on-behalf booking are available only to doctors and assistants.</p>
        <Link className="button" to="/app">
          Return to your home
        </Link>
      </section>
    );
  }

  return <Outlet context={user} />;
}

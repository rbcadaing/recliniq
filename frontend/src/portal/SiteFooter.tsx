import { Link } from "react-router-dom";
import Brand from "../Brand";
import type { User } from "../api";

type Props = {
  user?: User | null;
};

function linkFor(user: User | null | undefined, path: string) {
  return user ? path : `/login?next=${encodeURIComponent(path)}`;
}

export default function SiteFooter({ user }: Props) {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="footer-brand">
          <Brand to="/" />
          <p>Simple clinic scheduling and connected care for every visit.</p>
        </div>
        <div>
          <strong>Get care</strong>
          <Link to={linkFor(user, "/app/book")}>Book a consultation</Link>
          <Link to={linkFor(user, "/app/history")}>Visit history</Link>
          <Link to={linkFor(user, "/app/alerts")}>Alerts</Link>
        </div>
        <div>
          <strong>Clinic staff</strong>
          <Link to={linkFor(user, "/app/schedule")}>Plot a schedule</Link>
          <Link to={linkFor(user, "/app/on-behalf")}>Book for a patient</Link>
          <Link to="/login">Staff sign in</Link>
        </div>
      </div>
      <div className="site-footer-legal">© {new Date().getFullYear()} RecLinq. Care, connected.</div>
    </footer>
  );
}

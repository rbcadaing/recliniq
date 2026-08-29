import { Link, useNavigate } from "react-router-dom";
import Brand from "../Brand";
import { setToken, type User } from "../api";

type Props = {
  user: User | null;
};

export default function SiteHeader({ user }: Props) {
  const navigate = useNavigate();

  function logout() {
    setToken(null);
    navigate("/");
  }

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Brand to="/" />
        <nav className="site-actions" aria-label="Account">
          {user ? (
            <>
              <span className="account-label">
                <strong>{user.display_name}</strong>
                <small>{user.role}</small>
              </span>
              <Link className="button button-outline" to="/app">
                Manage
              </Link>
              <button className="button button-quiet" type="button" onClick={logout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <Link className="button button-quiet" to="/login">
                Sign in
              </Link>
              <Link className="button" to="/register">
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

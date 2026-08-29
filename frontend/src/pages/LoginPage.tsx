import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, safeNext, setToken } from "../api";

export default function LoginPage() {
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const [email, setEmail] = useState("doctor@example.com");
  const [password, setPassword] = useState("DoctorPass1!");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(r.access_token);
      nav(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-card">
        <span className="eyebrow">Welcome back</span>
        <h1>Sign in to RecLinq</h1>
        <p className="muted">Manage your consultations, records, and clinic schedule.</p>
        <form className="stack" onSubmit={onSubmit}>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required autoComplete="username" />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            autoComplete="current-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit">Sign in</button>
        </form>
        <p>
          New patient? <Link to={`/register?next=${encodeURIComponent(next)}`}>Register</Link>
        </p>
      </section>
    </div>
  );
}

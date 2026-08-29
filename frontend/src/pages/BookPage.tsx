import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import AvailabilityCalendar from "../portal/AvailabilityCalendar";

type Practitioner = { id: number; display_name: string };
type Slot = { starts_at: string };

export default function BookPage() {
  const [practitioners, setPractitioners] = useState<Practitioner[]>([]);
  const [pid, setPid] = useState<number | "">("");
  const [day, setDay] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [chosen, setChosen] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Practitioner[]>("/practitioners")
      .then((rows) => {
        setPractitioners(rows);
        if (rows[0]) setPid(rows[0].id);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load practitioners"));
  }, []);

  useEffect(() => {
    if (pid === "" || !day) {
      setSlots([]);
      setChosen("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api<Slot[]>(`/practitioners/${pid}/availability?date=${day}`)
      .then((rows) => {
        if (cancelled) return;
        setSlots(rows);
        setChosen(rows[0]?.starts_at ?? "");
      })
      .catch((err) => {
        if (cancelled) return;
        setSlots([]);
        setError(err instanceof Error ? err.message : "Failed to load times");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pid, day, msg]);

  async function book(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await api("/bookings", {
        method: "POST",
        body: JSON.stringify({ practitioner_id: pid, starts_at: chosen }),
      });
      setMsg(`Booked for ${new Date(chosen).toLocaleString()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <section className="stack">
      <h1>Book a visit</h1>
      <label>
        Practitioner
        <select value={pid} onChange={(e) => setPid(Number(e.target.value))}>
          {practitioners.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name}
            </option>
          ))}
        </select>
      </label>
      <div>
        <span className="field-label">Date</span>
        <AvailabilityCalendar practitionerId={pid} value={day} onChange={setDay} />
      </div>
      <form className="stack" onSubmit={book}>
        <label>
          Time
          <select value={chosen} onChange={(e) => setChosen(e.target.value)} required disabled={slots.length === 0}>
            <option value="">{loading ? "Loading…" : "Select a slot"}</option>
            {slots.map((s) => (
              <option key={s.starts_at} value={s.starts_at}>
                {new Date(s.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </option>
            ))}
          </select>
        </label>
        {!loading && day && slots.length === 0 && (
          <p className="muted">No open times on this date. Try another date.</p>
        )}
        <button type="submit" disabled={!chosen}>
          Confirm booking
        </button>
      </form>
      {msg && <p>{msg}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

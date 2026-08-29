import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import AvailabilityCalendar from "../portal/AvailabilityCalendar";

type Practitioner = { id: number; display_name: string };
type Patient = { id: number; email: string; display_name: string };
type Slot = { starts_at: string };

export default function OnBehalfPage() {
  const [practitioners, setPractitioners] = useState<Practitioner[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [pid, setPid] = useState<number | "">("");
  const [patientId, setPatientId] = useState<number | "">("");
  const [day, setDay] = useState("");
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [chosen, setChosen] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Practitioner[]>("/practitioners").then((rows) => {
      setPractitioners(rows);
      if (rows[0]) setPid(rows[0].id);
    });
    api<Patient[]>("/patients").then((rows) => {
      setPatients(rows);
      if (rows[0]) setPatientId(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (pid === "" || !day) {
      setSlots([]);
      setChosen("");
      return;
    }
    let cancelled = false;
    setLoading(true);
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
      await api("/bookings/on-behalf", {
        method: "POST",
        body: JSON.stringify({
          patient_id: patientId,
          practitioner_id: pid,
          starts_at: chosen,
        }),
      });
      setMsg(`Booked for ${new Date(chosen).toLocaleString()}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <section className="stack">
      <h1>Book for a patient</h1>
      <label>
        Patient
        <select value={patientId} onChange={(e) => setPatientId(Number(e.target.value))}>
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name} ({p.email})
            </option>
          ))}
        </select>
      </label>
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
        <button type="submit" disabled={!chosen || patientId === ""}>
          Confirm
        </button>
      </form>
      {msg && <p>{msg}</p>}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

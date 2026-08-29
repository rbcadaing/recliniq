import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";

type Practitioner = { id: number; display_name: string };
type Hours = { id: number; weekday: number; start_time: string; end_time: string };
type Ex = { id: number; closed_on: string | null; reason: string };

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function SchedulePage() {
  const [practitioners, setPractitioners] = useState<Practitioner[]>([]);
  const [pid, setPid] = useState<number | "">("");
  const [hours, setHours] = useState<Hours[]>([]);
  const [exceptions, setExceptions] = useState<Ex[]>([]);
  const [weekday, setWeekday] = useState(0);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("12:00");
  const [closedOn, setClosedOn] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<Practitioner[]>("/practitioners").then((rows) => {
      setPractitioners(rows);
      if (rows[0]) setPid(rows[0].id);
    });
  }, []);

  useEffect(() => {
    if (pid === "") return;
    api<Hours[]>(`/practitioners/${pid}/hours`).then(setHours);
    api<Ex[]>(`/practitioners/${pid}/exceptions`).then(setExceptions);
  }, [pid]);

  async function addHours(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/hours", {
        method: "POST",
        body: JSON.stringify({
          practitioner_id: pid,
          weekday,
          start_time: `${start}:00`,
          end_time: `${end}:00`,
        }),
      });
      if (pid !== "") setHours(await api(`/practitioners/${pid}/hours`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function addClosed(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/exceptions", {
        method: "POST",
        body: JSON.stringify({ practitioner_id: pid, closed_on: closedOn, reason: "closed" }),
      });
      if (pid !== "") setExceptions(await api(`/practitioners/${pid}/exceptions`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <section className="stack">
      <h1>Clinic hours</h1>
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
      <form className="stack" onSubmit={addHours}>
        <label>
          Weekday
          <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
            {DAYS.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          Start
          <input type="time" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          End
          <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button type="submit">Save hours</button>
      </form>
      <ul>
        {hours.map((h) => (
          <li key={h.id}>
            {DAYS[h.weekday]} {h.start_time}–{h.end_time}
          </li>
        ))}
      </ul>
      <form className="stack" onSubmit={addClosed}>
        <label>
          Closed date
          <input type="date" value={closedOn} onChange={(e) => setClosedOn(e.target.value)} required />
        </label>
        <button type="submit">Mark closed</button>
      </form>
      <ul>
        {exceptions.map((x) => (
          <li key={x.id}>
            {x.closed_on ?? "block"} {x.reason}
          </li>
        ))}
      </ul>
      {error && <p className="error">{error}</p>}
    </section>
  );
}

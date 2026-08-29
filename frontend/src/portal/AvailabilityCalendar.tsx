import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Props = {
  practitionerId: number | "";
  value: string;
  onChange: (isoDate: string) => void;
};

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function todayIso(): string {
  return isoDate(new Date());
}

function monthLabel(year: number, month: number): string {
  return new Date(year, month, 1).toLocaleString(undefined, { month: "long", year: "numeric" });
}

function cellsFor(year: number, month: number): (string | null)[] {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const cells: (string | null)[] = Array.from({ length: offset }, () => null);
  for (let day = 1; day <= lastDay; day++) {
    cells.push(`${year}-${pad(month + 1)}-${pad(day)}`);
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export default function AvailabilityCalendar({ practitionerId, value, onChange }: Props) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [openDays, setOpenDays] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const cells = useMemo(() => cellsFor(year, month), [year, month]);
  const canPrev = year > now.getFullYear() || month > now.getMonth();
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (practitionerId === "") return;
    const startDate = new Date(year, month, 1);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const rangeStart = startDate < today ? today : startDate;
    const rangeEnd = new Date(year, month + 1, 0);
    if (rangeEnd < today) {
      setOpenDays(new Set());
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api<string[]>(
      `/practitioners/${practitionerId}/available-dates?start=${isoDate(rangeStart)}&end=${isoDate(rangeEnd)}`,
    )
      .then((dates) => {
        if (cancelled) return;
        const next = new Set(dates);
        setOpenDays(next);
        if (dates.length === 0) {
          if (valueRef.current) onChange("");
          return;
        }
        if (!next.has(valueRef.current)) onChange(dates[0]);
      })
      .catch((err) => {
        if (cancelled) return;
        setOpenDays(new Set());
        setError(err instanceof Error ? err.message : "Failed to load dates");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [practitionerId, year, month]);

  function shift(delta: number) {
    const next = new Date(year, month + delta, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth());
  }

  return (
    <div className="calendar">
      <div className="calendar-toolbar">
        <button type="button" className="calendar-nav" onClick={() => shift(-1)} disabled={!canPrev} aria-label="Previous month">
          ‹
        </button>
        <strong>{monthLabel(year, month)}</strong>
        <button type="button" className="calendar-nav" onClick={() => shift(1)} aria-label="Next month">
          ›
        </button>
      </div>
      <div className="calendar-weekdays">
        {WEEKDAYS.map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div className="calendar-grid" aria-label="Available dates">
        {cells.map((iso, i) => {
          if (!iso) return <span key={`e-${i}`} className="calendar-empty" />;
          const enabled = openDays.has(iso);
          const selected = value === iso;
          return (
            <button
              key={iso}
              type="button"
              className={`calendar-day${enabled ? " is-open" : ""}${selected ? " is-selected" : ""}`}
              disabled={!enabled}
              onClick={() => onChange(iso)}
            >
              {Number(iso.slice(-2))}
            </button>
          );
        })}
      </div>
      {loading && <p className="muted">Finding open days…</p>}
      {!loading && openDays.size === 0 && <p className="muted">No open dates this month. Try another month.</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}

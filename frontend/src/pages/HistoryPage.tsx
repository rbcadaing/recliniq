import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Visit = {
  id: number;
  starts_at: string;
  booking_status: string;
  notes: string;
  patient_id: number;
};

type Patient = { id: number; display_name: string; email: string };

export default function HistoryPage() {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientId, setPatientId] = useState<string>("");
  const [error, setError] = useState("");
  const [meRole, setMeRole] = useState("");

  useEffect(() => {
    api<{ role: string }>("/auth/me").then((u) => {
      setMeRole(u.role);
      if (u.role !== "patient") {
        api<Patient[]>("/patients").then(setPatients);
      }
    });
    api<Visit[]>("/visits").then(setVisits).catch((e) => setError(e.message));
  }, []);

  async function filter() {
    const q = patientId ? `/visits?patient_id=${patientId}` : "/visits";
    setVisits(await api(q));
  }

  return (
    <section className="stack">
      <h1>Visit history</h1>
      {meRole !== "patient" && (
        <div className="stack">
          <label>
            Patient
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)}>
              <option value="">All</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" onClick={filter}>
            Filter
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <ul className="list">
        {visits.map((v) => (
          <li key={v.id}>
            <Link to={`/app/visits/${v.id}`}>
              {new Date(v.starts_at).toLocaleString()} — {v.booking_status}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

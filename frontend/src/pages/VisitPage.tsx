import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api, apiUrl, authHeader } from "../api";

type Visit = {
  id: number;
  notes: string;
  booking_status: string;
  starts_at: string;
  cancelled_by_user_id: number | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  booking_id: number;
};

type Doc = { id: number; filename: string; content_type: string };

export default function VisitPage() {
  const { id } = useParams();
  const [visit, setVisit] = useState<Visit | null>(null);
  const [notes, setNotes] = useState("");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const v = await api<Visit>(`/visits/${id}`);
      setVisit(v);
      setNotes(v.notes);
      setDocs(await api(`/visits/${id}/documents`));
    } catch (err) {
      setVisit(null);
      setError(err instanceof Error ? err.message : "Not found");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function save(e: FormEvent) {
    e.preventDefault();
    await api(`/visits/${id}`, { method: "PATCH", body: JSON.stringify({ notes }) });
    await load();
  }

  async function cancel(e: FormEvent) {
    e.preventDefault();
    if (!visit) return;
    await api(`/bookings/${visit.booking_id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    await load();
  }

  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = e.currentTarget.elements.namedItem("file") as HTMLInputElement;
    if (!input.files?.[0]) return;
    const body = new FormData();
    body.append("file", input.files[0]);
    const headers = new Headers(authHeader());
    const res = await fetch(apiUrl(`/visits/${id}/documents`), { method: "POST", headers, body });
    if (!res.ok) {
      setError("Upload failed");
      return;
    }
    await load();
  }

  if (error && !visit) return <p className="error">{error}</p>;
  if (!visit) return <p>Loading…</p>;

  return (
    <section className="stack">
      <h1>Visit</h1>
      <p>{new Date(visit.starts_at).toLocaleString()}</p>
      <p>Status: {visit.booking_status}</p>
      {visit.cancelled_at && (
        <p>
          Cancelled at {new Date(visit.cancelled_at).toLocaleString()} by user {visit.cancelled_by_user_id}
          {visit.cancel_reason ? ` — ${visit.cancel_reason}` : ""}
        </p>
      )}
      <form className="stack" onSubmit={save}>
        <label>
          Notes
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={5} />
        </label>
        <button type="submit">Save notes</button>
      </form>
      {visit.booking_status === "booked" && (
        <form className="stack" onSubmit={cancel}>
          <label>
            Cancel reason
            <input value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
          <button type="submit">Cancel booking</button>
        </form>
      )}
      <h2>Documents</h2>
      <form className="stack" onSubmit={upload}>
        <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" />
        <button type="submit">Upload</button>
      </form>
      <ul>
        {docs.map((d) => (
          <li key={d.id}>
            <a href={apiUrl(`/visits/${id}/documents/${d.id}`)} onClick={async (ev) => {
              ev.preventDefault();
              const res = await fetch(apiUrl(`/visits/${id}/documents/${d.id}`), { headers: authHeader() });
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = d.filename;
              a.click();
            }}>
              {d.filename}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

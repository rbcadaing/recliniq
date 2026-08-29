import { useEffect, useState } from "react";
import { api } from "../api";

type Alert = { id: number; event_type: string; body: string; read_at: string | null; created_at: string };

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  async function load() {
    setAlerts(await api("/alerts"));
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="stack">
      <h1>Alerts</h1>
      <ul className="list">
        {alerts.map((a) => (
          <li key={a.id} className={a.read_at ? "muted" : ""}>
            <strong>{a.event_type}</strong>
            <p>{a.body}</p>
            {!a.read_at && (
              <button type="button" onClick={async () => {
                await api(`/alerts/${a.id}/read`, { method: "POST" });
                await load();
              }}>
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

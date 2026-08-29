const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type User = {
  id: number;
  tenant_id: number;
  email: string;
  role: "patient" | "doctor" | "assistant";
  display_name: string;
};

function token(): string | null {
  return sessionStorage.getItem("token");
}

export function setToken(t: string | null) {
  if (t) sessionStorage.setItem("token", t);
  else sessionStorage.removeItem("token");
}

export function safeNext(value: string | null): string {
  if (!value || (value !== "/app" && !value.startsWith("/app/"))) return "/app";
  return value;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const t = token();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function apiUrl(path: string): string {
  return `${API}${path}`;
}

export function authHeader(): Record<string, string> {
  const t = token();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

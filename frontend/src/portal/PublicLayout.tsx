import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { api, setToken, type User } from "../api";
import SiteFooter from "./SiteFooter";
import SiteHeader from "./SiteHeader";

export default function PublicLayout() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!sessionStorage.getItem("token")) return;
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setToken(null));
  }, []);

  return (
    <div className="site">
      <SiteHeader user={user} />
      <main>
        <Outlet context={user} />
      </main>
      <SiteFooter user={user} />
    </div>
  );
}

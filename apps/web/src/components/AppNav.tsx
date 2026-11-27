import { Link } from "@tanstack/react-router";
import type { UserRole } from "../api/auth";
import { useAuth } from "../context/useAuth";
import { NotificationCenter } from "./NotificationCenter";

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrator",
  supervisor: "Nadrzędny",
  user: "Podrzędny",
};

export function AppNav() {
  const { user, logout } = useAuth();

  if (!user) {
    return null;
  }

  const roleLabel = user.role ? ROLE_LABELS[user.role] : ROLE_LABELS.user;

  return (
    <header className="app-nav">
      <a className="skip-link" href="#main-content">
        Przejdź do treści
      </a>
      <div className="app-nav-left">
        <span className="app-nav-brand">MALINOIS</span>
        <nav aria-label="Nawigacja główna" className="app-nav-links">
          <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/">
            Dashboard
          </Link>
          <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/cases">
            Sprawy
          </Link>
          <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/import">
            Import / Edytor
          </Link>
          <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/archive">
            Archiwum
          </Link>
          <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/settings">
            Ustawienia
          </Link>
          {user.role === "admin" && (
            <Link className="nav-link" activeProps={{ className: "nav-link nav-link-active" }} to="/admin">
              Panel administratora
            </Link>
          )}
        </nav>
      </div>
      <div className="app-nav-right">
        <NotificationCenter />
        <span className="role-badge" data-role={user.role ?? "user"}>
          {roleLabel}
        </span>
        <span className="app-nav-email">{user.email}</span>
        <button className="nav-logout-btn" type="button" onClick={logout}>
          wyloguj
        </button>
      </div>
    </header>
  );
}

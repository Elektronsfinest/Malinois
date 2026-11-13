import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "../context/useAuth";

export function DashboardPage() {
  const { token, user, isLoading, authError, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !token) {
      void navigate({ to: "/login", replace: true });
    }
  }, [isLoading, token, navigate]);

  async function handleLogout() {
    logout();
    await navigate({ to: "/login", replace: true });
  }

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }

  if (authError) {
    return (
      <main>
        <p role="alert">{authError}</p>
        <button type="button" onClick={handleLogout}>
          Wyloguj
        </button>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <main>
      <h1>Dashboard</h1>
      <p>Witaj, {user.email}!</p>
      <button type="button" onClick={handleLogout}>
        Wyloguj
      </button>
    </main>
  );
}

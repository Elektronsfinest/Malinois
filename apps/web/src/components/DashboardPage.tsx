import { useAuth } from "../context/useAuth";

export function DashboardPage() {
  const { user, isLoading, authError, logout } = useAuth();

  function handleLogout() {
    logout();
  }

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }

  if (authError) {
    return (
      <div className="dashboard-container">
        <div className="glow-orb glow-orb-1" />
        <div className="glow-orb glow-orb-2" />
        <main className="dashboard-card">
          <p role="alert">{authError}</p>
          <button className="logout-btn" type="button" onClick={handleLogout}>
            wyloguj
          </button>
        </main>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="dashboard-container">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />

      <h1 className="brand-title">MALINOIS</h1>

      <main className="dashboard-card">
        <h1>Dashboard</h1>
        <p className="dashboard-greeting">Witaj, {user.email}!</p>
        <button className="logout-btn" type="button" onClick={handleLogout}>
          wyloguj
        </button>
      </main>
    </div>
  );
}

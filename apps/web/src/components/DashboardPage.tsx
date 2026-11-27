import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { fetchDashboardSummaryRequest, type DashboardSummary } from "../api/dashboard";
import { useAuth } from "../context/useAuth";
import { AppNav } from "./AppNav";

function formatDateTimePl(iso: string | null): string {
  if (!iso) {
    return "Brak danych";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) {
    return iso;
  }
  return d.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DashboardPage() {
  const { token, user, isLoading, authError, logout } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    let cancelled = false;

    const load = () => {
      fetchDashboardSummaryRequest(token)
        .then((data) => {
          if (!cancelled) {
            setSummary(data);
            setSummaryError(null);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setSummaryError(
              err instanceof Error ? err.message : "Nie udało się pobrać podsumowania."
            );
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoadingSummary(false);
          }
        });
    };

    load();
    const intervalId = window.setInterval(load, 5 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [token, user]);

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
          <button className="logout-btn" type="button" onClick={logout}>
            wyloguj
          </button>
        </main>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const threshold = summary?.notification_threshold_days ?? user.notification_threshold_days ?? 7;

  return (
    <div className="app-shell">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />
      <AppNav />

      <main className="cases-main" id="main-content">
        <div className="cases-header">
          <div>
            <h1>Dashboard</h1>
            <p className="cases-subtitle">Witaj, {user.email}!</p>
          </div>
          <div className="cases-header-actions">
            {user.role === "admin" && summary && (
              <span className="dashboard-meta-chip">
                Ostatni import: <strong>{formatDateTimePl(summary.import_last_at)}</strong>
              </span>
            )}
            <Link className="primary-pill-btn nav-button-link" to="/cases">
              Przejdź do spraw
            </Link>
          </div>
        </div>

        {summaryError && (
          <div className="error-banner" role="alert">
            {summaryError}
          </div>
        )}

        {loadingSummary && !summary ? (
          <div className="stats-grid" aria-label="Ładowanie statystyk">
            {[0, 1, 2, 3].map((idx) => (
              <div key={idx} className="stat-card stat-card-skeleton" aria-hidden="true" />
            ))}
          </div>
        ) : (
          summary && (
            <>
              <section className="stats-grid" aria-label="Podsumowanie spraw">
                <Link
                  className="stat-card"
                  to="/cases"
                  search={{ status: "open" }}
                >
                  <span className="stat-card-label">Otwarte sprawy</span>
                  <span className="stat-card-value">{summary.open_cases}</span>
                  {summary.total_cases != null && (
                    <span className="stat-card-hint">Wszystkie aktywne: {summary.total_cases}</span>
                  )}
                </Link>

                <Link
                  className={`stat-card${summary.overdue_cases > 0 ? " stat-card-overdue" : ""}`}
                  to="/cases"
                  search={{ overdue: true, status: "open" }}
                >
                  <span className="stat-card-label">Zaległe</span>
                  <span className="stat-card-value">{summary.overdue_cases}</span>
                  <span className="stat-card-hint">Termin przed dzisiejszą datą</span>
                </Link>

                <Link
                  className={`stat-card${summary.due_soon > 0 ? " stat-card-warning" : ""}`}
                  to="/cases"
                  search={{ due_soon: true, status: "open" }}
                >
                  <span className="stat-card-label">
                    Zbliżający się termin (≤ {threshold} dni)
                  </span>
                  <span className="stat-card-value">{summary.due_soon}</span>
                  <span className="stat-card-hint">Wymagają uwagi wkrótce</span>
                </Link>

                <Link
                  className="stat-card"
                  to="/cases"
                  search={{ status: "closed" }}
                >
                  <span className="stat-card-label">Zamknięte w tym miesiącu</span>
                  <span className="stat-card-value">{summary.closed_this_month}</span>
                  <span className="stat-card-hint">Bieżący miesiąc kalendarzowy</span>
                </Link>
              </section>

              {summary.team_summary && summary.team_summary.length > 0 && (
                <section className="cases-table-card" aria-label="Mój zespół">
                  <h2 className="section-heading">
                    {user.role === "admin" ? "Obciążenie pracowników" : "Mój zespół"}
                  </h2>
                  <div className="table-scroll">
                    <table className="cases-table">
                      <thead>
                        <tr>
                          <th scope="col">Pracownik</th>
                          <th scope="col">Otwarte</th>
                          <th scope="col">Zaległe</th>
                          <th scope="col">Zbliżające się</th>
                          <th scope="col">Podgląd</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.team_summary.map((member) => (
                          <tr key={member.user_id}>
                            <td>
                              {member.email}
                              {!member.is_active && (
                                <span className="inactive-tag"> (nieaktywny)</span>
                              )}
                            </td>
                            <td>{member.open_cases}</td>
                            <td>
                              <span
                                className={
                                  member.overdue_cases > 0
                                    ? "urgency-badge urgency-overdue"
                                    : undefined
                                }
                              >
                                {member.overdue_cases}
                              </span>
                            </td>
                            <td>
                              <span
                                className={
                                  member.due_soon > 0 ? "urgency-badge urgency-warning" : undefined
                                }
                              >
                                {member.due_soon}
                              </span>
                            </td>
                            <td>
                              <Link
                                className="row-btn nav-button-link"
                                to="/cases"
                                search={{ assigned_to: member.user_id }}
                              >
                                Pokaż sprawy
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </>
          )
        )}
      </main>
    </div>
  );
}

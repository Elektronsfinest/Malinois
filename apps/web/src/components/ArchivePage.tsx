import { useEffect, useState } from "react";
import {
  BulkConflictError,
  bulkCasesRequest,
  fetchCasesRequest,
  restoreCaseRequest,
  type BulkConflictItem,
  type CaseItem,
} from "../api/cases";
import { useAuth } from "../context/useAuth";
import { formatPolishDate } from "../utils/dates";
import { AppNav } from "./AppNav";

export function ArchivePage() {
  const { token, user, isLoading } = useAuth();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [reloadTick, setReloadTick] = useState(0);
  const pageSize = 50;
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<number | null>(null);

  // Bulk selection state (supervisor & admin only)
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showBulkConfirm, setShowBulkConfirm] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkConflicts, setBulkConflicts] = useState<BulkConflictItem[] | null>(null);

  const canRestoreRole = user?.role === "admin" || user?.role === "supervisor";
  const restorableCases = cases.filter((c) => !c.is_readonly_archive);

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    let cancelled = false;
    fetchCasesRequest(token, page, pageSize, true)
      .then((data) => {
        if (!cancelled) {
          setCases(data.items);
          setTotal(data.total);
          setSelectedIds([]);
          setErrorMsg(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : "Nie udało się pobrać archiwum.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, user, page, reloadTick]);

  async function handleRestore(c: CaseItem) {
    if (!token) {
      return;
    }
    setRestoringId(c.id);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      await restoreCaseRequest(token, c.id, c.version);
      setCases((prev) => prev.filter((item) => item.id !== c.id));
      setSelectedIds((prev) => prev.filter((id) => id !== c.id));
      setTotal((t) => Math.max(0, t - 1));
      setStatusMsg(`Przywrócono sprawę „${c.title}” do aktywnej listy.`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się przywrócić sprawy.");
    } finally {
      setRestoringId(null);
    }
  }

  function toggleRowSelection(caseId: number) {
    setSelectedIds((prev) =>
      prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]
    );
  }

  function toggleSelectAll() {
    if (selectedIds.length === restorableCases.length && restorableCases.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(restorableCases.map((c) => c.id));
    }
  }

  async function executeBulkRestore() {
    if (!token || selectedIds.length === 0) {
      return;
    }
    const items = cases
      .filter((c) => selectedIds.includes(c.id))
      .map((c) => ({ id: c.id, version: c.version }));
    setBulkBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    setBulkConflicts(null);
    try {
      const res = await bulkCasesRequest(token, { items, action: "restore" });
      setShowBulkConfirm(false);
      setSelectedIds([]);
      setReloadTick((t) => t + 1);
      setStatusMsg(`Zaktualizowano ${res.affected_count} spraw`);
    } catch (err: unknown) {
      setShowBulkConfirm(false);
      if (err instanceof BulkConflictError) {
        setBulkConflicts(err.conflicts);
      } else {
        setErrorMsg(err instanceof Error ? err.message : "Nie udało się przywrócić zaznaczonych spraw.");
      }
    } finally {
      setBulkBusy(false);
    }
  }

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }
  if (!user) {
    return null;
  }

  const allSelected = restorableCases.length > 0 && selectedIds.length === restorableCases.length;

  return (
    <div className="app-shell">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />
      <AppNav />

      <main className="cases-main" id="main-content">
        <div className="cases-header">
          <div>
            <h1>Archiwum spraw</h1>
            <p className="cases-subtitle">Zarchiwizowane sprawy: {total}</p>
          </div>
        </div>

        {statusMsg && (
          <div className="status-banner" role="status" aria-live="polite">
            {statusMsg}
          </div>
        )}
        {errorMsg && (
          <div className="error-banner" role="alert">
            {errorMsg}
          </div>
        )}
        {bulkConflicts && (
          <div className="error-banner" role="alert">
            <p>
              Konflikt wersji dla spraw:{" "}
              {bulkConflicts.map((c) => `#${c.case_id} (v${c.expected_version} → v${c.current_version})`).join(", ")}.
            </p>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => {
                setBulkConflicts(null);
                setReloadTick((t) => t + 1);
              }}
            >
              Odśwież tabelę
            </button>
          </div>
        )}

        <section className="cases-table-card" aria-label="Tabela zarchiwizowanych spraw">
          {loading ? (
            <p className="cases-empty">Wczytywanie archiwum...</p>
          ) : cases.length === 0 ? (
            <p className="cases-empty">Brak zarchiwizowanych spraw w Twoim zakresie.</p>
          ) : (
            <div className="table-scroll">
              <table className="cases-table">
                <thead>
                  <tr>
                    {canRestoreRole && (
                      <th scope="col" className="checkbox-col">
                        <input
                          type="checkbox"
                          aria-label="Zaznacz wszystkie na tej stronie"
                          checked={allSelected}
                          disabled={bulkBusy || restorableCases.length === 0}
                          onChange={toggleSelectAll}
                        />
                      </th>
                    )}
                    <th scope="col">Numer sprawy</th>
                    <th scope="col">Tytuł</th>
                    <th scope="col">Klient</th>
                    <th scope="col">Przypisany</th>
                    <th scope="col">Termin realizacji</th>
                    <th scope="col">Dostęp</th>
                    {canRestoreRole && <th scope="col">Akcje</th>}
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.id}>
                      {canRestoreRole && (
                        <td className="checkbox-col">
                          {!c.is_readonly_archive && (
                            <input
                              type="checkbox"
                              aria-label={`Zaznacz sprawę ${c.title}`}
                              checked={selectedIds.includes(c.id)}
                              disabled={bulkBusy}
                              onChange={() => toggleRowSelection(c.id)}
                            />
                          )}
                        </td>
                      )}
                      <td>{c.case_number ?? "—"}</td>
                      <td className="case-title-cell">{c.title}</td>
                      <td>{c.client_name}</td>
                      <td>
                        {c.assigned_to_email}
                        {!c.assigned_to_is_active && (
                          <span className="inactive-tag"> (nieaktywny)</span>
                        )}
                      </td>
                      <td>{formatPolishDate(c.deadline)}</td>
                      <td>
                        {c.is_readonly_archive ? (
                          <span className="status-pill status-closed">Tylko odczyt (poprzedni)</span>
                        ) : (
                          <span className="status-pill status-closed">Zarchiwizowana</span>
                        )}
                      </td>
                      {canRestoreRole && (
                        <td>
                          {!c.is_readonly_archive && (
                            <button
                              className="row-btn row-btn-complete"
                              type="button"
                              disabled={restoringId === c.id || bulkBusy}
                              onClick={() => void handleRestore(c)}
                            >
                              Przywróć
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > pageSize && (
            <div className="pagination-bar" aria-label="Stronicowanie archiwum">
              <span>
                Strona {page} z {Math.max(1, Math.ceil(total / pageSize))}
              </span>
              <div className="pagination-buttons">
                <button
                  className="secondary-btn"
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Poprzednia
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  disabled={page * pageSize >= total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Następna
                </button>
              </div>
            </div>
          )}
        </section>
      </main>

      {canRestoreRole && selectedIds.length > 0 && (
        <div className="bulk-action-bar" role="region" aria-label="Akcje zbiorcze archiwum">
          <span>Zaznaczono: {selectedIds.length} spraw</span>
          <div className="bulk-action-buttons">
            <button
              className="primary-pill-btn"
              type="button"
              disabled={bulkBusy}
              onClick={() => setShowBulkConfirm(true)}
            >
              {bulkBusy ? "Przywracanie..." : "Przywróć zaznaczone"}
            </button>
            <button
              className="secondary-btn"
              type="button"
              disabled={bulkBusy}
              onClick={() => setSelectedIds([])}
            >
              Odznacz wszystkie
            </button>
          </div>
        </div>
      )}

      {showBulkConfirm && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-restore-confirm-h"
          >
            <h2 id="bulk-restore-confirm-h">Przywrócić zaznaczone sprawy?</h2>
            <p className="cases-subtitle">
              Zostanie przywróconych <strong>{selectedIds.length}</strong> spraw do aktywnej listy.
            </p>
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                disabled={bulkBusy}
                onClick={() => void executeBulkRestore()}
              >
                {bulkBusy ? "Przywracanie..." : "Zatwierdź przywrócenie"}
              </button>
              <button
                className="secondary-btn"
                type="button"
                disabled={bulkBusy}
                onClick={() => setShowBulkConfirm(false)}
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { fetchAssignableUsersRequest, type AssignableUser, type CaseStatus } from "../api/cases";
import {
  commitWorkingCopyRequest,
  createSnapshotCopyRequest,
  deleteWorkingCopyRequest,
  downloadWorkingCopyRequest,
  getWorkingCopyRequest,
  listWorkingCopiesRequest,
  patchWorkingCopyRequest,
  uploadWorkingCopyRequest,
  type ConflictResolution,
  type WorkingCopyCommitResult,
  type WorkingCopyDetail,
  type WorkingCopyRow,
  type WorkingCopySummary,
} from "../api/importCopies";
import { useAuth } from "../context/useAuth";
import { AppNav } from "./AppNav";

function formatExpiry(iso: string): string {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) {
    return iso;
  }
  return dt.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ImportPage() {
  const { token, user, isLoading } = useAuth();
  const [copies, setCopies] = useState<WorkingCopySummary[]>([]);
  const [activeCopy, setActiveCopy] = useState<WorkingCopyDetail | null>(null);
  const [editedRows, setEditedRows] = useState<Record<number, WorkingCopyRow>>({});
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);
  const [defaultAssigneeId, setDefaultAssigneeId] = useState<number | "">("");

  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [commitSummary, setCommitSummary] = useState<WorkingCopyCommitResult | null>(null);
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isAdmin = user?.role === "admin";
  const canUpload = user?.role === "admin" || user?.role === "supervisor";

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    let cancelled = false;

    listWorkingCopiesRequest(token)
      .then((list) => {
        if (!cancelled) {
          setCopies(list);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : "Nie udało się pobrać listy kopii.");
        }
      });

    if (user.role === "admin" || user.role === "supervisor") {
      fetchAssignableUsersRequest(token)
        .then((users) => {
          if (!cancelled) {
            setAssignableUsers(users);
            setDefaultAssigneeId((prev) => (prev === "" && users.length > 0 ? users[0].id : prev));
          }
        })
        .catch(() => {
          // Handled gracefully
        });
    }

    return () => {
      cancelled = true;
    };
  }, [token, user]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && showCommitModal) {
        setShowCommitModal(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showCommitModal]);

  const extraColumnKeys = useMemo(() => {
    if (!activeCopy) {
      return [];
    }
    const keys: string[] = [];
    const seen = new Set<string>();
    for (const r of activeCopy.rows) {
      for (const k of Object.keys(r.extra_columns || {})) {
        if (!seen.has(k)) {
          seen.add(k);
          keys.push(k);
        }
      }
    }
    return keys;
  }, [activeCopy]);

  function selectCopyDetail(detail: WorkingCopyDetail) {
    setActiveCopy(detail);
    setEditedRows({});
    setCommitSummary(null);
    setCopies((prev) => {
      const summary: WorkingCopySummary = {
        id: detail.id,
        source_type: detail.source_type,
        label: detail.label,
        row_count: detail.row_count,
        error_count: detail.error_count,
        conflict_count: detail.conflict_count,
        created_at: detail.created_at,
        expires_at: detail.expires_at,
      };
      const exists = prev.some((c) => c.id === detail.id);
      return exists ? prev.map((c) => (c.id === detail.id ? summary : c)) : [summary, ...prev];
    });
  }

  async function handleSelectCopy(copyId: number) {
    if (!token) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const detail = await getWorkingCopyRequest(token, copyId);
      selectCopyDetail(detail);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się otworzyć kopii.");
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(file: File) {
    if (!token) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const detail = await uploadWorkingCopyRequest(
        token,
        file,
        defaultAssigneeId === "" ? null : Number(defaultAssigneeId)
      );
      selectCopyDetail(detail);
      setStatusMsg(`Wczytano kopię roboczą „${detail.label}” (${detail.row_count} wierszy).`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się wgrać pliku.");
    } finally {
      setBusy(false);
    }
  }

  async function handleFileUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) {
      return;
    }
    await uploadFile(file);
  }

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (!busy && !isDragging) {
      setIsDragging(true);
    }
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  async function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (busy) {
      return;
    }
    const file = e.dataTransfer.files?.[0];
    if (file) {
      await uploadFile(file);
    }
  }

  async function handleCreateSnapshot() {
    if (!token) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const detail = await createSnapshotCopyRequest(token);
      selectCopyDetail(detail);
      setStatusMsg(`Utworzono kopię bieżących spraw (${detail.row_count} wierszy).`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się utworzyć kopii.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteCopy(copyId: number) {
    if (!token) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    try {
      await deleteWorkingCopyRequest(token, copyId);
      setCopies((prev) => prev.filter((c) => c.id !== copyId));
      if (activeCopy?.id === copyId) {
        setActiveCopy(null);
        setEditedRows({});
      }
      setStatusMsg("Usunięto kopię roboczą.");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się usunąć kopii.");
    } finally {
      setBusy(false);
    }
  }

  function updateLocalRow(baseRow: WorkingCopyRow, patch: Partial<WorkingCopyRow>) {
    setEditedRows((prev) => {
      const current = prev[baseRow.row_index] ?? baseRow;
      return {
        ...prev,
        [baseRow.row_index]: { ...current, ...patch },
      };
    });
  }

  async function handleSaveCopyEdits() {
    if (!token || !activeCopy) {
      return;
    }
    const dirtyRows = Object.values(editedRows);
    if (dirtyRows.length === 0) {
      return;
    }
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const patches = dirtyRows.map((r) => ({
        row_index: r.row_index,
        case_number: r.case_number,
        title: r.title,
        client_name: r.client_name,
        assigned_to_email: r.assigned_to_email,
        ...(isAdmin ? { deadline: r.deadline || null, date_filed: r.date_filed || null } : {}),
        status: r.status,
        note: r.note,
        extra_columns: r.extra_columns,
        resolution: r.resolution,
      }));
      const updated = await patchWorkingCopyRequest(token, activeCopy.id, patches);
      selectCopyDetail(updated);
      setStatusMsg("Zapisano zmiany w kopii roboczej.");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się zapisać zmian w kopii.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCommitConfirmed() {
    if (!token || !activeCopy) {
      return;
    }
    setShowCommitModal(false);
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      // Save any pending local grid edits before committing
      const dirtyRows = Object.values(editedRows);
      if (dirtyRows.length > 0) {
        const patches = dirtyRows.map((r) => ({
          row_index: r.row_index,
          case_number: r.case_number,
          title: r.title,
          client_name: r.client_name,
          assigned_to_email: r.assigned_to_email,
          ...(isAdmin ? { deadline: r.deadline || null, date_filed: r.date_filed || null } : {}),
          status: r.status,
          note: r.note,
          extra_columns: r.extra_columns,
          resolution: r.resolution,
        }));
        const saved = await patchWorkingCopyRequest(token, activeCopy.id, patches);
        selectCopyDetail(saved);
      }

      const result = await commitWorkingCopyRequest(token, activeCopy.id);
      setCommitSummary(result);
      const refreshed = await getWorkingCopyRequest(token, activeCopy.id);
      selectCopyDetail(refreshed);
      setCommitSummary(result);
      setStatusMsg(
        `Zatwierdzono zmiany: utworzono ${result.created}, zaktualizowano ${result.updated}, pominięto ${result.skipped}.`
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się zatwierdzić kopii.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDownload() {
    if (!token || !activeCopy) {
      return;
    }
    setErrorMsg(null);
    try {
      await downloadWorkingCopyRequest(token, activeCopy.id);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się pobrać pliku Excel.");
    }
  }

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }

  if (!user) {
    return null;
  }

  const hasDirtyRows = Object.keys(editedRows).length > 0;
  const canCommit =
    Boolean(activeCopy) &&
    (activeCopy?.error_count ?? 0) === 0 &&
    (activeCopy?.conflict_count ?? 0) === 0 &&
    !busy;

  return (
    <div className="app-shell">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />
      <AppNav />

      <main className="cases-main" id="main-content">
        <div className="cases-header">
          <div>
            <h1>Edytor pliku Excel (kopie robocze)</h1>
            <p className="cases-subtitle">
              Aplikacja zawsze pracuje na kopiach (TTL 24h, maks. 5 aktywnych kopii). Zmiany trafiają
              do bazy dopiero po zatwierdzeniu.
            </p>
          </div>
          <div className="cases-header-actions">
            <button
              className="primary-pill-btn"
              type="button"
              disabled={busy}
              onClick={() => void handleCreateSnapshot()}
            >
              Otwórz kopię bieżących spraw
            </button>
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

        {commitSummary && (
          <section className="cases-table-card" aria-label="Podsumowanie zatwierdzenia">
            <h2>Podsumowanie zatwierdzenia</h2>
            <p className="cases-subtitle">
              Utworzono: <strong>{commitSummary.created}</strong> · Zaktualizowano:{" "}
              <strong>{commitSummary.updated}</strong> · Pominięto:{" "}
              <strong>{commitSummary.skipped}</strong> · Konflikty wersji:{" "}
              <strong>{commitSummary.conflicts.length}</strong> · Błędy:{" "}
              <strong>{commitSummary.errors.length}</strong>
            </p>
            {commitSummary.conflicts.map((c) => (
              <p className="warning-banner" key={`conf-${c.row}`}>
                Wiersz {c.row}: {c.reason}
              </p>
            ))}
          </section>
        )}

        {canUpload && (
          <section className="cases-table-card import-upload-card" aria-label="Wgrywanie pliku Excel">
            <div className="upload-controls">
              <div className="form-field">
                <label htmlFor="default-assignee">Domyślny pracownik dla wgranych wierszy</label>
                <select
                  id="default-assignee"
                  value={defaultAssigneeId}
                  onChange={(e) => setDefaultAssigneeId(Number(e.target.value))}
                >
                  {assignableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email}
                      {u.is_active ? "" : " (nieaktywny)"}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="excel-file-input">Wgraj plik Excel (.xlsx / .xls, maks. 10 MB)</label>
                <div
                  className={`upload-dropzone${isDragging ? " upload-dropzone-active" : ""}${busy ? " upload-dropzone-disabled" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-label="Przeciągnij i upuść plik Excel lub kliknij, aby wybrać"
                  onClick={() => !busy && fileInputRef.current?.click()}
                  onKeyDown={(e) => {
                    if (!busy && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  onDragEnter={handleDragOver}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => void handleDrop(e)}
                >
                  <p className="dropzone-title">
                    {isDragging
                      ? "Upuść plik Excel tutaj..."
                      : "Przeciągnij i upuść plik Excel (.xlsx / .xls) tutaj lub kliknij, aby wybrać"}
                  </p>
                  <p className="dropzone-hint">
                    Maksymalny rozmiar: 10 MB · Przetwarzanie wyłącznie w pamięci
                  </p>
                  <input
                    ref={fileInputRef}
                    id="excel-file-input"
                    className="sr-only-file-input"
                    type="file"
                    accept=".xlsx,.xls"
                    disabled={busy}
                    onChange={(e) => void handleFileUpload(e)}
                  />
                </div>
              </div>
            </div>
          </section>
        )}

        <section className="cases-table-card" aria-label="Aktywne kopie robocze">
          <h2>Twoje aktywne kopie ({copies.length}/5)</h2>
          {copies.length === 0 ? (
            <p className="cases-empty">
              Brak aktywnych kopii roboczych. Wgraj plik Excel lub otwórz kopię bieżących spraw.
            </p>
          ) : (
            <div className="copies-list">
              {copies.map((c) => (
                <div
                  key={c.id}
                  className={`copy-chip${activeCopy?.id === c.id ? " copy-chip-active" : ""}`}
                >
                  <button
                    className="copy-chip-select"
                    type="button"
                    onClick={() => void handleSelectCopy(c.id)}
                  >
                    <strong>{c.label}</strong>
                    <span>
                      {c.row_count} wierszy · wygasa {formatExpiry(c.expires_at)}
                    </span>
                    {(c.error_count > 0 || c.conflict_count > 0) && (
                      <span className="inactive-tag">
                        Błędy: {c.error_count} · Konflikty: {c.conflict_count}
                      </span>
                    )}
                  </button>
                  <button
                    className="row-btn"
                    type="button"
                    aria-label={`Usuń kopię ${c.label}`}
                    onClick={() => void handleDeleteCopy(c.id)}
                  >
                    Usuń
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>

        {activeCopy && (
          <section className="cases-table-card" aria-label="Arkusz kopii roboczej">
            <div className="cases-header">
              <div>
                <h2>{activeCopy.label}</h2>
                <p className="cases-subtitle">
                  Wierszy: {activeCopy.row_count} · Błędy walidacji: {activeCopy.error_count} ·
                  Nierozwiązane konflikty: {activeCopy.conflict_count}
                </p>
              </div>
              <div className="cases-header-actions">
                <button
                  className="secondary-btn"
                  type="button"
                  disabled={!hasDirtyRows || busy}
                  onClick={() => void handleSaveCopyEdits()}
                >
                  Zapisz kopię
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  disabled={busy}
                  onClick={() => void handleDownload()}
                >
                  Pobierz Excel (.xlsx)
                </button>
                <button
                  className="primary-pill-btn"
                  type="button"
                  disabled={!canCommit && !hasDirtyRows}
                  onClick={() => setShowCommitModal(true)}
                >
                  Zatwierdź zmiany
                </button>
              </div>
            </div>

            <div className="table-scroll">
              <table className="cases-table import-grid-table">
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">Walidacja / Konflikt</th>
                    <th scope="col">Nr sprawy</th>
                    <th scope="col">Tytuł</th>
                    <th scope="col">Klient</th>
                    <th scope="col">Przypisany</th>
                    <th scope="col">Termin</th>
                    <th scope="col">Data wpływu</th>
                    <th scope="col">Status</th>
                    {extraColumnKeys.map((k) => (
                      <th scope="col" key={k}>
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeCopy.rows.map((baseRow) => {
                    const row = editedRows[baseRow.row_index] ?? baseRow;
                    return (
                      <tr key={row.row_index}>
                        <td>{row.row_index}</td>
                        <td>
                          {row.errors.map((err, i) => (
                            <div className="urgency-badge urgency-overdue" key={`e-${i}`}>
                              {err}
                            </div>
                          ))}
                          {row.warnings.map((w, i) => (
                            <div className="urgency-badge urgency-due_soon" key={`w-${i}`}>
                              {w}
                            </div>
                          ))}
                          {row.conflict && (
                            <select
                              aria-label={`Rozwiązanie konfliktu dla wiersza ${row.row_index}`}
                              value={row.resolution ?? ""}
                              onChange={(e) =>
                                updateLocalRow(baseRow, {
                                  resolution: (e.target.value || null) as ConflictResolution | null,
                                })
                              }
                            >
                              <option value="">Wybierz (duplikat w bazie)</option>
                              <option value="skip">Pomiń (skip)</option>
                              <option value="update_existing">Nadpisz (update_existing)</option>
                            </select>
                          )}
                        </td>
                        <td>
                          <input
                            aria-label={`Nr sprawy wiersz ${row.row_index}`}
                            className="grid-input"
                            type="text"
                            disabled={!isAdmin}
                            value={row.case_number ?? ""}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { case_number: e.target.value || null })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Tytuł wiersz ${row.row_index}`}
                            className="grid-input"
                            type="text"
                            value={row.title ?? ""}
                            onChange={(e) => updateLocalRow(baseRow, { title: e.target.value })}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Klient wiersz ${row.row_index}`}
                            className="grid-input"
                            type="text"
                            value={row.client_name ?? ""}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { client_name: e.target.value })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Przypisany wiersz ${row.row_index}`}
                            className="grid-input"
                            type="text"
                            disabled={!isAdmin}
                            value={row.assigned_to_email ?? ""}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { assigned_to_email: e.target.value })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Termin wiersz ${row.row_index}`}
                            className="grid-input"
                            type="date"
                            disabled={!isAdmin}
                            value={row.deadline ?? ""}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { deadline: e.target.value || null })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Data wpływu wiersz ${row.row_index}`}
                            className="grid-input"
                            type="date"
                            disabled={!isAdmin}
                            value={row.date_filed ?? ""}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { date_filed: e.target.value || null })
                            }
                          />
                        </td>
                        <td>
                          <select
                            aria-label={`Status wiersz ${row.row_index}`}
                            className="grid-input"
                            value={row.status}
                            onChange={(e) =>
                              updateLocalRow(baseRow, { status: e.target.value as CaseStatus })
                            }
                          >
                            <option value="open">Otwarta</option>
                            <option value="closed">Zamknięta</option>
                          </select>
                        </td>
                        {extraColumnKeys.map((k) => (
                          <td key={`${row.row_index}-${k}`}>
                            <input
                              aria-label={`${k} wiersz ${row.row_index}`}
                              className="grid-input"
                              type="text"
                              value={row.extra_columns?.[k] ?? ""}
                              onChange={(e) =>
                                updateLocalRow(baseRow, {
                                  extra_columns: {
                                    ...(row.extra_columns || {}),
                                    [k]: e.target.value,
                                  },
                                })
                              }
                            />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {showCommitModal && activeCopy && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="commit-confirm-heading"
          >
            <h2 id="commit-confirm-heading">Zatwierdzić zmiany do bazy spraw?</h2>
            <p className="cases-subtitle">
              Kopia „{activeCopy.label}” ({activeCopy.row_count} wierszy) zostanie zastosowana do
              aktywnej bazy spraw. Przed zapisem zostanie utworzony automatyczny punkt przywracania.
            </p>
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => void handleCommitConfirmed()}
              >
                Potwierdź i zapisz
              </button>
              <button
                className="secondary-btn"
                type="button"
                onClick={() => setShowCommitModal(false)}
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

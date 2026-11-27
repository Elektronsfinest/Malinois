import { useEffect, useState, type FormEvent } from "react";
import {
  createAdminUserRequest,
  DeactivationConflictError,
  downloadAdminBackupRequest,
  fetchAdminAuditLogRequest,
  fetchAdminBackupsRequest,
  fetchAdminSettingsRequest,
  fetchAdminUsersRequest,
  resetAdminUserPasswordRequest,
  triggerAdminBackupRequest,
  updateAdminSettingsRequest,
  updateAdminUserRequest,
  type AdminAuditLogEntry,
  type BackupLogEntry,
} from "../api/admin";
import type { User, UserRole } from "../api/auth";
import { useAuth } from "../context/useAuth";
import { AppNav } from "./AppNav";

type AdminTab = "users" | "settings" | "audit" | "backups";

const BACKUP_TYPE_LABELS: Record<BackupLogEntry["backup_type"], string> = {
  automated: "Automatyczna",
  manual: "Ręczna",
  pre_import: "Przed importem",
};

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrator",
  supervisor: "Nadrzędny",
  user: "Podrzędny",
};

function formatDateTime(iso: string): string {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AdminPage() {
  const { token, user, isLoading, refreshUser } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Users tab state
  const [users, setUsers] = useState<User[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<UserRole>("user");
  const [newSupervisorId, setNewSupervisorId] = useState<number | "">("");

  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editRole, setEditRole] = useState<UserRole>("user");
  const [editSupervisorId, setEditSupervisorId] = useState<number | "">("");
  const [editActive, setEditActive] = useState(true);
  const [reassignCasesTo, setReassignCasesTo] = useState<number | "">("");
  const [reassignSubsTo, setReassignSubsTo] = useState<number | "">("");
  const [conflictInfo, setConflictInfo] = useState<{
    caseIds: number[];
    subIds: number[];
  } | null>(null);

  const [revealedPassword, setRevealedPassword] = useState<{
    email: string;
    password: string;
  } | null>(null);

  // Settings tab state
  const [thresholdDays, setThresholdDays] = useState<number>(7);
  const [savingSettings, setSavingSettings] = useState(false);

  // Audit Log tab state
  const [auditItems, setAuditItems] = useState<AdminAuditLogEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditActionFilter, setAuditActionFilter] = useState("");

  // Backups tab state
  const [backups, setBackups] = useState<BackupLogEntry[]>([]);
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [downloadTarget, setDownloadTarget] = useState<BackupLogEntry | null>(null);
  const [downloadPassword, setDownloadPassword] = useState("");
  const [downloadingBackup, setDownloadingBackup] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || user?.role !== "admin") return;
    let cancelled = false;

    fetchAdminUsersRequest(token)
      .then((list) => {
        if (!cancelled) setUsers(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(err instanceof Error ? err.message : "Błąd pobierania użytkowników.");
      });

    fetchAdminSettingsRequest(token)
      .then((s) => {
        if (!cancelled) setThresholdDays(s.notification_threshold_days);
      })
      .catch(() => {
        // Ignore
      });

    return () => {
      cancelled = true;
    };
  }, [token, user]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || activeTab !== "audit") return;
    let cancelled = false;

    fetchAdminAuditLogRequest(token, auditActionFilter)
      .then((res) => {
        if (!cancelled) {
          setAuditItems(res.items);
          setAuditTotal(res.total);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(err instanceof Error ? err.message : "Błąd pobierania audytu.");
      });

    return () => {
      cancelled = true;
    };
  }, [token, user, activeTab, auditActionFilter]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || activeTab !== "backups") return;
    let cancelled = false;

    fetchAdminBackupsRequest(token)
      .then((list) => {
        if (!cancelled) setBackups(list);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(
            err instanceof Error ? err.message : "Błąd pobierania listy kopii zapasowych."
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, user, activeTab]);

  async function handleCreateBackup() {
    if (!token) return;
    setCreatingBackup(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const created = await triggerAdminBackupRequest(token);
      setBackups((prev) => [created, ...prev]);
      setStatusMsg(`Utworzono kopię zapasową: ${created.filename}`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się utworzyć kopii zapasowej.");
    } finally {
      setCreatingBackup(false);
    }
  }

  async function handleDownloadBackupSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !downloadTarget) return;
    setDownloadingBackup(true);
    setDownloadError(null);
    try {
      const blob = await downloadAdminBackupRequest(
        token,
        downloadTarget.filename,
        downloadPassword
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = downloadTarget.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setDownloadTarget(null);
      setDownloadPassword("");
      setStatusMsg(`Pobrano kopię zapasową: ${downloadTarget.filename}`);
    } catch (err: unknown) {
      setDownloadError(
        err instanceof Error ? err.message : "Nie udało się pobrać kopii zapasowej."
      );
    } finally {
      setDownloadingBackup(false);
    }
  }

  if (isLoading) return <p>Ładowanie...</p>;
  if (!user || user.role !== "admin" || !token) return null;

  const managers = users.filter((u) => u.is_active && (u.role === "supervisor" || u.role === "admin"));
  const activeUsers = users.filter((u) => u.is_active);
  const emailById = new Map(users.map((u) => [u.id, u.email]));

  function openEditModal(target: User) {
    setEditingUser(target);
    setEditRole(target.role);
    setEditSupervisorId(target.supervisor_id ?? "");
    setEditActive(target.is_active);
    setReassignCasesTo("");
    setReassignSubsTo("");
    setConflictInfo(null);
    setErrorMsg(null);
  }

  async function handleCreateUser(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const created = await createAdminUserRequest(token, {
        email: newEmail.trim(),
        password: newPassword,
        role: newRole,
        supervisor_id: newRole === "user" && newSupervisorId !== "" ? Number(newSupervisorId) : null,
      });
      setUsers((prev) => [...prev, created]);
      setShowCreateModal(false);
      setNewEmail("");
      setNewPassword("");
      setNewRole("user");
      setNewSupervisorId("");
      setStatusMsg(`Utworzono użytkownika ${created.email} (wymagana zmiana hasła przy logowaniu).`);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się utworzyć użytkownika.");
    }
  }

  async function handleUpdateUser(e: FormEvent) {
    e.preventDefault();
    if (!token || !editingUser) return;
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const updated = await updateAdminUserRequest(token, editingUser.id, {
        role: editRole,
        supervisor_id:
          editRole === "user" ? (editSupervisorId === "" ? null : Number(editSupervisorId)) : null,
        is_active: editActive,
        ...(reassignCasesTo !== "" ? { reassign_cases_to: Number(reassignCasesTo) } : {}),
        ...(reassignSubsTo !== "" ? { reassign_subordinates_to: Number(reassignSubsTo) } : {}),
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setEditingUser(null);
      setConflictInfo(null);
      setStatusMsg(`Zaktualizowano użytkownika ${updated.email}.`);
    } catch (err: unknown) {
      if (err instanceof DeactivationConflictError) {
        setConflictInfo({
          caseIds: err.blockingCaseIds,
          subIds: err.blockingSubordinateIds,
        });
        setErrorMsg(err.message);
      } else {
        setErrorMsg(err instanceof Error ? err.message : "Nie udało się zaktualizować użytkownika.");
      }
    }
  }

  async function handleResetPassword(target: User) {
    if (!token) return;
    setErrorMsg(null);
    try {
      const tempPwd = await resetAdminUserPasswordRequest(token, target.id);
      setRevealedPassword({ email: target.email, password: tempPwd });
      setUsers((prev) =>
        prev.map((u) => (u.id === target.id ? { ...u, must_change_password: true } : u))
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się zresetować hasła.");
    }
  }

  async function handleSaveSettings(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSavingSettings(true);
    setErrorMsg(null);
    setStatusMsg(null);
    try {
      const saved = await updateAdminSettingsRequest(token, Number(thresholdDays));
      setThresholdDays(saved.notification_threshold_days);
      await refreshUser();
      setStatusMsg(
        `Zapisano próg powiadomień: ${saved.notification_threshold_days} dni (aktywny natychmiast).`
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się zapisać ustawień.");
    } finally {
      setSavingSettings(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />
      <AppNav />

      <main className="cases-main" id="main-content">
        <div className="cases-header">
          <div>
            <h1>Panel administratora</h1>
            <p className="cases-subtitle">Zarządzanie użytkownikami, ustawieniami, audytem i kopiami</p>
          </div>
        </div>

        <div className="admin-tabs" role="tablist" aria-label="Zakładki panelu administratora">
          <button
            role="tab"
            type="button"
            aria-selected={activeTab === "users"}
            className={`admin-tab-btn${activeTab === "users" ? " admin-tab-active" : ""}`}
            onClick={() => setActiveTab("users")}
          >
            Użytkownicy
          </button>
          <button
            role="tab"
            type="button"
            aria-selected={activeTab === "settings"}
            className={`admin-tab-btn${activeTab === "settings" ? " admin-tab-active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            Ustawienia systemowe
          </button>
          <button
            role="tab"
            type="button"
            aria-selected={activeTab === "audit"}
            className={`admin-tab-btn${activeTab === "audit" ? " admin-tab-active" : ""}`}
            onClick={() => setActiveTab("audit")}
          >
            Dziennik audytu
          </button>
          <button
            role="tab"
            type="button"
            aria-selected={activeTab === "backups"}
            className={`admin-tab-btn${activeTab === "backups" ? " admin-tab-active" : ""}`}
            onClick={() => setActiveTab("backups")}
          >
            Kopie zapasowe
          </button>
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

        {activeTab === "users" && (
          <section className="cases-table-card" aria-label="Zarządzanie użytkownikami">
            <div className="cases-header">
              <h2>Użytkownicy ({users.length})</h2>
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => {
                  setErrorMsg(null);
                  setShowCreateModal(true);
                }}
              >
                Dodaj użytkownika
              </button>
            </div>
            <div className="table-scroll">
              <table className="cases-table">
                <thead>
                  <tr>
                    <th scope="col">Email</th>
                    <th scope="col">Rola</th>
                    <th scope="col">Przełożony</th>
                    <th scope="col">Status</th>
                    <th scope="col">Akcje</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td className="case-title-cell">{u.email}</td>
                      <td>
                        <span className="role-badge">{ROLE_LABELS[u.role]}</span>
                      </td>
                      <td>{u.supervisor_id ? (emailById.get(u.supervisor_id) ?? `#${u.supervisor_id}`) : "—"}</td>
                      <td>
                        <span className={`status-pill ${u.is_active ? "status-open" : "status-closed"}`}>
                          {u.is_active ? "Aktywny" : "Nieaktywny"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="row-btn"
                          type="button"
                          onClick={() => openEditModal(u)}
                        >
                          Edytuj
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeTab === "settings" && (
          <section className="cases-table-card" aria-label="Ustawienia systemowe">
            <h2>Ustawienia systemowe</h2>
            <form className="editor-form" onSubmit={handleSaveSettings}>
              <div className="form-field">
                <label htmlFor="admin-threshold-days">
                  Próg powiadomień przed terminem (dni, 1–365)
                </label>
                <input
                  id="admin-threshold-days"
                  type="number"
                  min={1}
                  max={365}
                  value={thresholdDays}
                  onChange={(e) => setThresholdDays(Number(e.target.value))}
                />
              </div>
              <div className="editor-actions">
                <button className="primary-pill-btn" type="submit" disabled={savingSettings}>
                  {savingSettings ? "Zapisywanie..." : "Zapisz ustawienia"}
                </button>
              </div>
            </form>
          </section>
        )}

        {activeTab === "audit" && (
          <section className="cases-table-card" aria-label="Dziennik audytu">
            <div className="cases-header">
              <h2>Dziennik audytu ({auditTotal})</h2>
              <div className="form-field">
                <label htmlFor="audit-action-filter">Filtr akcji</label>
                <select
                  id="audit-action-filter"
                  value={auditActionFilter}
                  onChange={(e) => setAuditActionFilter(e.target.value)}
                >
                  <option value="">Wszystkie akcje</option>
                  <option value="user_created">user_created</option>
                  <option value="role_changed">role_changed</option>
                  <option value="supervisor_changed">supervisor_changed</option>
                  <option value="user_activated">user_activated</option>
                  <option value="user_deactivated">user_deactivated</option>
                  <option value="password_reset">password_reset</option>
                  <option value="settings_updated">settings_updated</option>
                </select>
              </div>
            </div>
            {auditItems.length === 0 ? (
              <p className="cases-empty">Brak wpisów w dzienniku audytu.</p>
            ) : (
              <div className="table-scroll">
                <table className="cases-table">
                  <thead>
                    <tr>
                      <th scope="col">Data</th>
                      <th scope="col">Administrator</th>
                      <th scope="col">Akcja</th>
                      <th scope="col">ID celu</th>
                      <th scope="col">Szczegóły</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditItems.map((entry) => (
                      <tr key={entry.id}>
                        <td>{formatDateTime(entry.created_at)}</td>
                        <td>{entry.actor_email}</td>
                        <td>
                          <span className="role-badge">{entry.action}</span>
                        </td>
                        <td>{entry.target_user_id ?? "—"}</td>
                        <td>{entry.details ? JSON.stringify(entry.details) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {activeTab === "backups" && (
          <section className="cases-table-card" aria-label="Kopie zapasowe">
            <div className="cases-header">
              <div>
                <h2>Kopie zapasowe</h2>
                <p className="cases-subtitle">
                  Kopie bazy danych przechowywane przez 14 dni (automatyczne o 02:00 UTC, przed
                  importem oraz ręczne).
                </p>
              </div>
              <button
                className="primary-pill-btn"
                type="button"
                disabled={creatingBackup}
                onClick={() => void handleCreateBackup()}
              >
                {creatingBackup ? "Tworzenie kopii..." : "Utwórz kopię zapasową"}
              </button>
            </div>
            {backups.length === 0 ? (
              <p className="cases-empty">Brak zapisanych kopii zapasowych.</p>
            ) : (
              <div className="table-scroll">
                <table className="cases-table">
                  <thead>
                    <tr>
                      <th scope="col">Data i czas</th>
                      <th scope="col">Typ</th>
                      <th scope="col">Nazwa pliku</th>
                      <th scope="col">Rozmiar</th>
                      <th scope="col">Akcje</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backups.map((b) => (
                      <tr key={b.id}>
                        <td>{formatDateTime(b.created_at)}</td>
                        <td>
                          <span className="role-badge">
                            {BACKUP_TYPE_LABELS[b.backup_type] ?? b.backup_type}
                          </span>
                        </td>
                        <td>{b.filename}</td>
                        <td>{formatFileSize(b.size_bytes)}</td>
                        <td>
                          <button
                            className="row-btn"
                            type="button"
                            onClick={() => {
                              setDownloadTarget(b);
                              setDownloadPassword("");
                              setDownloadError(null);
                            }}
                          >
                            Pobierz
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>

      {downloadTarget && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="backup-download-heading"
          >
            <h2 id="backup-download-heading">Potwierdź hasło administratora</h2>
            <p className="cases-subtitle">
              Pobranie kopii <strong>{downloadTarget.filename}</strong> wymaga ponownego podania
              hasła i zostanie zapisane w dzienniku audytu.
            </p>
            {downloadError && (
              <div className="error-banner" role="alert">
                {downloadError}
              </div>
            )}
            <form className="editor-form" onSubmit={handleDownloadBackupSubmit}>
              <div className="form-field">
                <label htmlFor="backup-download-password">Hasło administratora</label>
                <input
                  id="backup-download-password"
                  type="password"
                  required
                  autoFocus
                  value={downloadPassword}
                  onChange={(e) => setDownloadPassword(e.target.value)}
                />
              </div>
              <div className="editor-actions">
                <button className="primary-pill-btn" type="submit" disabled={downloadingBackup}>
                  {downloadingBackup ? "Pobieranie..." : "Potwierdź i pobierz"}
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  disabled={downloadingBackup}
                  onClick={() => setDownloadTarget(null)}
                >
                  Anuluj
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="create-user-h">
            <h2 id="create-user-h">Dodaj użytkownika</h2>
            <form className="editor-form" onSubmit={handleCreateUser}>
              <div className="form-field">
                <label htmlFor="cu-email">Email</label>
                <input
                  id="cu-email"
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="cu-password">Hasło tymczasowe (min. 12 znaków)</label>
                <input
                  id="cu-password"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="cu-role">Rola</label>
                <select
                  id="cu-role"
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as UserRole)}
                >
                  <option value="user">Podrzędny (user)</option>
                  <option value="supervisor">Nadrzędny (supervisor)</option>
                  <option value="admin">Administrator (admin)</option>
                </select>
              </div>
              {newRole === "user" && (
                <div className="form-field">
                  <label htmlFor="cu-supervisor">Przełożony (opcjonalny)</label>
                  <select
                    id="cu-supervisor"
                    value={newSupervisorId}
                    onChange={(e) =>
                      setNewSupervisorId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">Brak</option>
                    {managers.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.email} ({ROLE_LABELS[m.role]})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="editor-actions">
                <button className="primary-pill-btn" type="submit">
                  Utwórz użytkownika
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                >
                  Anuluj
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editingUser && (
        <div className="modal-backdrop">
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="edit-user-h">
            <h2 id="edit-user-h">Edytuj: {editingUser.email}</h2>
            <form className="editor-form" onSubmit={handleUpdateUser}>
              <div className="form-field">
                <label htmlFor="eu-role">Rola</label>
                <select
                  id="eu-role"
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value as UserRole)}
                >
                  <option value="user">Podrzędny (user)</option>
                  <option value="supervisor">Nadrzędny (supervisor)</option>
                  <option value="admin">Administrator (admin)</option>
                </select>
              </div>
              {editRole === "user" && (
                <div className="form-field">
                  <label htmlFor="eu-supervisor">Przełożony</label>
                  <select
                    id="eu-supervisor"
                    value={editSupervisorId}
                    onChange={(e) =>
                      setEditSupervisorId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  >
                    <option value="">Brak</option>
                    {managers
                      .filter((m) => m.id !== editingUser.id)
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.email}
                        </option>
                      ))}
                  </select>
                </div>
              )}
              <div className="form-field">
                <label htmlFor="eu-active">Status konta</label>
                <select
                  id="eu-active"
                  value={editActive ? "true" : "false"}
                  onChange={(e) => setEditActive(e.target.value === "true")}
                >
                  <option value="true">Aktywny</option>
                  <option value="false">Nieaktywny</option>
                </select>
              </div>

              {conflictInfo && conflictInfo.caseIds.length > 0 && (
                <div className="form-field">
                  <label htmlFor="eu-reassign-cases">
                    Przepisz aktywne sprawy ({conflictInfo.caseIds.length}) do:
                  </label>
                  <select
                    id="eu-reassign-cases"
                    required
                    value={reassignCasesTo}
                    onChange={(e) => setReassignCasesTo(Number(e.target.value))}
                  >
                    <option value="">Wybierz pracownika</option>
                    {activeUsers
                      .filter((u) => u.id !== editingUser.id)
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.email}
                        </option>
                      ))}
                  </select>
                </div>
              )}

              {conflictInfo && conflictInfo.subIds.length > 0 && (
                <div className="form-field">
                  <label htmlFor="eu-reassign-subs">
                    Przepisz podwładnych ({conflictInfo.subIds.length}) do:
                  </label>
                  <select
                    id="eu-reassign-subs"
                    required
                    value={reassignSubsTo}
                    onChange={(e) => setReassignSubsTo(Number(e.target.value))}
                  >
                    <option value="">Wybierz przełożonego</option>
                    {managers
                      .filter((m) => m.id !== editingUser.id)
                      .map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.email}
                        </option>
                      ))}
                  </select>
                </div>
              )}

              <div className="editor-actions">
                <button className="primary-pill-btn" type="submit">
                  Zapisz zmiany
                </button>
                {editingUser.id !== user.id && (
                  <button
                    className="secondary-btn"
                    type="button"
                    onClick={() => void handleResetPassword(editingUser)}
                  >
                    Reset hasła
                  </button>
                )}
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => setEditingUser(null)}
                >
                  Anuluj
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {revealedPassword && (
        <div className="modal-backdrop">
          <div className="modal-card" role="alertdialog" aria-modal="true" aria-labelledby="pwd-rev-h">
            <h2 id="pwd-rev-h">Nowe hasło tymczasowe</h2>
            <p className="cases-subtitle">
              Przekaż poniższe jednorazowe hasło użytkownikowi <strong>{revealedPassword.email}</strong>.
              Nie będzie można go ponownie wyświetlić.
            </p>
            <code className="temp-password-box">{revealedPassword.password}</code>
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => {
                  void navigator.clipboard?.writeText(revealedPassword.password);
                  setStatusMsg("Skopiowano hasło tymczasowe do schowka.");
                }}
              >
                Kopiuj hasło
              </button>
              <button
                className="secondary-btn"
                type="button"
                onClick={() => setRevealedPassword(null)}
              >
                Zamknij
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

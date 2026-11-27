import { useEffect, useState, type FormEvent } from "react";
import type { AssignableUser } from "../api/cases";
import {
  createCaseNoteRequest,
  deleteNoteRequest,
  fetchCaseHistoryRequest,
  fetchCaseNotesRequest,
  type CaseEditLogEntry,
  type CaseNoteItem,
} from "../api/historyNotes";
import { useAuth } from "../context/useAuth";

interface CaseEditorExtrasProps {
  caseId: number;
  caseVersion: number;
  assignableUsers: AssignableUser[];
}

const FIELD_LABELS: Record<string, string> = {
  created: "Utworzono sprawę",
  title: "Tytuł",
  client_name: "Klient",
  status: "Status",
  deadline: "Termin realizacji",
  date_filed: "Data wpływu",
  case_number: "Numer sprawy",
  assigned_to: "Przypisany pracownik",
  archived: "Archiwum",
};

function formatFieldName(name: string): string {
  if (name.startsWith("extra:")) {
    return name.slice(6);
  }
  return FIELD_LABELS[name] ?? name;
}

function formatPlDateTime(iso: string): string {
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

export function CaseEditorExtras({
  caseId,
  caseVersion,
  assignableUsers,
}: CaseEditorExtrasProps) {
  const { token, user } = useAuth();
  const [notes, setNotes] = useState<CaseNoteItem[]>([]);
  const [noteContent, setNoteContent] = useState("");
  const [subjectUserId, setSubjectUserId] = useState<number | "">("");
  const [savingNote, setSavingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<CaseEditLogEntry[]>([]);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [hasMoreHistory, setHasMoreHistory] = useState(false);

  const subjectOptions =
    assignableUsers.length > 0
      ? assignableUsers
      : user
        ? [{ id: user.id, email: user.email, role: user.role, is_active: user.is_active }]
        : [];

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;
    fetchCaseNotesRequest(token, caseId)
      .then((list) => {
        if (!cancelled) {
          setNotes(list);
          setNoteError(null);
        }
      })
      .catch(() => {
        // Degrade gracefully
      });

    return () => {
      cancelled = true;
    };
  }, [token, caseId]);

  useEffect(() => {
    if (!token || !historyOpen) {
      return;
    }
    let cancelled = false;
    fetchCaseHistoryRequest(token, caseId, 50, 0)
      .then((entries) => {
        if (!cancelled) {
          setHistory(entries);
          setHistoryOffset(entries.length);
          setHasMoreHistory(entries.length === 50);
        }
      })
      .catch(() => {
        // Degrade gracefully
      });

    return () => {
      cancelled = true;
    };
  }, [token, caseId, caseVersion, historyOpen]);

  async function handleAddNote(e: FormEvent) {
    e.preventDefault();
    if (!token || !noteContent.trim()) {
      return;
    }
    setSavingNote(true);
    setNoteError(null);
    try {
      const created = await createCaseNoteRequest(
        token,
        caseId,
        noteContent.trim(),
        subjectUserId === "" ? null : Number(subjectUserId)
      );
      setNotes((prev) => [created, ...prev]);
      setNoteContent("");
      setSubjectUserId("");
    } catch (err: unknown) {
      setNoteError(err instanceof Error ? err.message : "Nie udało się dodać notatki.");
    } finally {
      setSavingNote(false);
    }
  }

  async function handleDeleteNote(noteId: number) {
    if (!token) {
      return;
    }
    try {
      await deleteNoteRequest(token, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err: unknown) {
      setNoteError(err instanceof Error ? err.message : "Nie udało się usunąć notatki.");
    }
  }

  async function handleLoadMoreHistory() {
    if (!token) {
      return;
    }
    try {
      const more = await fetchCaseHistoryRequest(token, caseId, 50, historyOffset);
      setHistory((prev) => [...prev, ...more]);
      setHistoryOffset((prev) => prev + more.length);
      setHasMoreHistory(more.length === 50);
    } catch {
      // Ignore
    }
  }

  return (
    <div className="editor-extras">
      <section className="editor-subpanel" aria-label="Notatki do sprawy">
        <h3>Notatki ({notes.length})</h3>
        {noteError && (
          <div className="error-banner" role="alert">
            {noteError}
          </div>
        )}
        <form className="editor-form" onSubmit={handleAddNote}>
          <div className="form-field">
            <label htmlFor="case-note-subject">Dotyczy osoby (opcjonalne)</label>
            <select
              id="case-note-subject"
              value={subjectUserId}
              onChange={(e) =>
                setSubjectUserId(e.target.value === "" ? "" : Number(e.target.value))
              }
            >
              <option value="">Notatka ogólna do sprawy</option>
              {subjectOptions.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                  {u.is_active ? "" : " (nieaktywny)"}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="case-note-content">Treść notatki ({noteContent.length}/2000)</label>
            <textarea
              id="case-note-content"
              className="note-textarea"
              rows={3}
              maxLength={2000}
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
            />
          </div>
          <button
            className="secondary-btn"
            type="submit"
            disabled={savingNote || !noteContent.trim()}
          >
            Dodaj notatkę
          </button>
        </form>

        {notes.length > 0 && (
          <ul className="notif-list">
            {notes.map((n) => (
              <li className="notif-item" key={n.id}>
                <div className="notif-item-top">
                  <strong>{n.author_email}</strong>
                  <span className="notif-item-meta">{formatPlDateTime(n.created_at)}</span>
                </div>
                {n.subject_email && (
                  <span className="role-badge">Dotyczy: {n.subject_email}</span>
                )}
                <p className="note-content-text">{n.content}</p>
                {(user?.role === "admin" || user?.id === n.author_id) && (
                  <div className="notif-item-actions">
                    <button
                      className="row-btn"
                      type="button"
                      onClick={() => void handleDeleteNote(n.id)}
                    >
                      Usuń
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="editor-subpanel" aria-label="Historia zmian">
        <button
          className="history-toggle-btn"
          type="button"
          aria-expanded={historyOpen}
          onClick={() => setHistoryOpen((o) => !o)}
        >
          <span>Historia zmian</span>
          <span>{historyOpen ? "▲" : "▼"}</span>
        </button>

        {historyOpen && (
          <div className="history-list-wrap">
            {history.length === 0 ? (
              <p className="notif-empty">Brak zarejestrowanych zmian.</p>
            ) : (
              <ul className="notif-list">
                {history.map((h) => {
                  const isDateField = h.field_name === "deadline" || h.field_name === "date_filed";
                  return (
                    <li className="notif-item" key={h.id}>
                      <div className="notif-item-top">
                        <strong>{formatFieldName(h.field_name)}</strong>
                        {isDateField && <span className="role-badge">Admin</span>}
                      </div>
                      <p className="notif-item-meta">
                        {h.changed_by_email} · {formatPlDateTime(h.changed_at)}
                      </p>
                      <p className="note-content-text">
                        {h.old_value ?? "—"} → {h.new_value ?? "—"}
                      </p>
                      {h.reason && (
                        <p className="notif-item-meta">Powód: {h.reason}</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {hasMoreHistory && (
              <button
                className="secondary-btn"
                type="button"
                onClick={() => void handleLoadMoreHistory()}
              >
                Pokaż więcej
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import type { AssignableUser } from "../api/cases";
import {
  createPersonNoteRequest,
  deleteNoteRequest,
  fetchPersonNotesRequest,
  type CaseNoteItem,
} from "../api/historyNotes";
import { useAuth } from "../context/useAuth";

interface PersonNotesModalProps {
  users: AssignableUser[];
  onClose: () => void;
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

export function PersonNotesModal({ users, onClose }: PersonNotesModalProps) {
  const { token, user } = useAuth();
  const selectableUsers =
    users.length > 0
      ? users
      : user
        ? [{ id: user.id, email: user.email, role: user.role, is_active: user.is_active }]
        : [];

  const [selectedUserId, setSelectedUserId] = useState<number>(
    selectableUsers[0]?.id ?? user?.id ?? 0
  );
  const [notes, setNotes] = useState<CaseNoteItem[]>([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !selectedUserId) {
      return;
    }
    let cancelled = false;
    fetchPersonNotesRequest(token, selectedUserId)
      .then((list) => {
        if (!cancelled) {
          setNotes(list);
          setErrorMsg(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : "Nie udało się pobrać notatek.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, selectedUserId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !selectedUserId || !content.trim()) {
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const created = await createPersonNoteRequest(token, selectedUserId, content.trim());
      setNotes((prev) => [created, ...prev]);
      setContent("");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się dodać notatki.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(noteId: number) {
    if (!token) {
      return;
    }
    try {
      await deleteNoteRequest(token, noteId);
      setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Nie udało się usunąć notatki.");
    }
  }

  return (
    <div className="modal-backdrop">
      <div
        className="modal-card modal-notifications"
        role="dialog"
        aria-modal="true"
        aria-labelledby="person-notes-heading"
      >
        <div className="editor-header">
          <h2 id="person-notes-heading">Notatki o pracowniku</h2>
          <button
            className="icon-close-btn"
            type="button"
            aria-label="Zamknij notatki o pracowniku"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {selectableUsers.length > 1 && (
          <div className="form-field">
            <label htmlFor="person-note-user">Wybierz pracownika</label>
            <select
              id="person-note-user"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(Number(e.target.value))}
            >
              {selectableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                  {u.is_active ? "" : " (nieaktywny)"}
                </option>
              ))}
            </select>
          </div>
        )}

        {errorMsg && (
          <div className="error-banner" role="alert">
            {errorMsg}
          </div>
        )}

        <form className="editor-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="person-note-textarea">
              Nowa notatka ({content.length}/2000)
            </label>
            <textarea
              id="person-note-textarea"
              className="note-textarea"
              rows={3}
              maxLength={2000}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <div className="editor-actions">
            <button
              className="primary-pill-btn"
              type="submit"
              disabled={loading || !content.trim()}
            >
              Dodaj notatkę
            </button>
          </div>
        </form>

        <div className="notif-popup-scroll">
          {notes.length === 0 ? (
            <p className="notif-empty">Brak notatek dla tego pracownika.</p>
          ) : (
            <ul className="notif-list">
              {notes.map((n) => (
                <li className="notif-item" key={n.id}>
                  <div className="notif-item-top">
                    <strong>{n.author_email}</strong>
                    <span className="notif-item-meta">{formatPlDateTime(n.created_at)}</span>
                  </div>
                  <p className="note-content-text">{n.content}</p>
                  {(user?.role === "admin" || user?.id === n.author_id) && (
                    <div className="notif-item-actions">
                      <button
                        className="row-btn"
                        type="button"
                        onClick={() => void handleDelete(n.id)}
                      >
                        Usuń
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

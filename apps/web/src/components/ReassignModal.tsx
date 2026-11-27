import { useState, type FormEvent } from "react";
import type { AssignableUser } from "../api/cases";

interface ReassignModalProps {
  count: number;
  assignableUsers: AssignableUser[];
  busy: boolean;
  error: string | null;
  onConfirm: (newAssignedTo: number, reason: string) => void;
  onCancel: () => void;
}

export function ReassignModal({
  count,
  assignableUsers,
  busy,
  error,
  onConfirm,
  onCancel,
}: ReassignModalProps) {
  const activeUsers = assignableUsers.filter((u) => u.is_active);
  const [targetUserId, setTargetUserId] = useState<number | "">(
    activeUsers.length > 0 ? activeUsers[0].id : ""
  );
  const [reason, setReason] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (targetUserId === "") {
      return;
    }
    onConfirm(Number(targetUserId), reason.trim());
  }

  return (
    <div className="modal-backdrop">
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reassign-modal-heading"
      >
        <h2 id="reassign-modal-heading">
          {count === 1 ? "Przepisz sprawę" : `Przepisz zaznaczone sprawy (${count})`}
        </h2>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        <form className="editor-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="reassign-target-user">Nowy pracownik</label>
            <select
              id="reassign-target-user"
              required
              value={targetUserId}
              onChange={(e) => setTargetUserId(Number(e.target.value))}
            >
              {activeUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.email}
                </option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label htmlFor="reassign-reason">
              Powód przepisania (np. zastępstwo, urlop)
            </label>
            <input
              id="reassign-reason"
              type="text"
              maxLength={500}
              placeholder="Opcjonalnie — zapisze się w historii i notatkach"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          <div className="editor-actions">
            <button
              className="primary-pill-btn"
              type="submit"
              disabled={busy || targetUserId === ""}
            >
              {busy ? "Przepisywanie..." : "Zatwierdź przepisanie"}
            </button>
            <button
              className="secondary-btn"
              type="button"
              disabled={busy}
              onClick={onCancel}
            >
              Anuluj
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

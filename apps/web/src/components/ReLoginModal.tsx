import { useState, type FormEvent } from "react";
import { ApiError } from "../api/auth";
import { useAuth } from "../context/useAuth";
import { clearDraftsIfDifferentUser } from "../utils/draftStorage";

interface ReLoginModalProps {
  expectedEmail: string;
  onSuccess: (sameUser: boolean) => void;
  onCancel: () => void;
}

export function ReLoginModal({ expectedEmail, onSuccess, onCancel }: ReLoginModalProps) {
  const { authenticate, commitLogin } = useAuth();
  const [email, setEmail] = useState(expectedEmail);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("Podaj adres email i hasło.");
      return;
    }
    setSubmitting(true);
    try {
      const data = await authenticate(email.trim(), password);
      const sameUser =
        data.user.email.trim().toLowerCase() === expectedEmail.trim().toLowerCase();
      clearDraftsIfDifferentUser(data.user.email);
      commitLogin(data);
      onSuccess(sameUser);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Niepoprawny login lub hasło");
      } else {
        setError(err instanceof Error ? err.message : "Nie udało się ponownie zalogować.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="relogin-modal-heading"
      >
        <h2 id="relogin-modal-heading">Sesja wygasła — zaloguj się ponownie</h2>
        <p className="cases-subtitle">
          Twoje niezapisane zmiany zostały bezpiecznie zachowane w tej karcie. Zaloguj się ponownie
          jako <strong>{expectedEmail}</strong>, aby kontynuować edycję bez utraty danych.
        </p>
        {error && (
          <div className="error-banner" role="alert">
            {error}
          </div>
        )}
        <form className="editor-form" onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="relogin-email">Email</label>
            <input
              id="relogin-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="relogin-password">Hasło</label>
            <input
              id="relogin-password"
              type="password"
              required
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="editor-actions">
            <button className="primary-pill-btn" type="submit" disabled={submitting}>
              {submitting ? "Logowanie..." : "Zaloguj ponownie"}
            </button>
            <button className="secondary-btn" type="button" onClick={onCancel}>
              Anuluj
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

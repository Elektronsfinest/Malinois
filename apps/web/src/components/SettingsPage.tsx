import { useState, type FormEvent } from "react";
import {
  changePasswordRequest,
  updateMySettingsRequest,
  type UIFontSize,
  type UISettings,
  type UITheme,
} from "../api/auth";
import { applyUiSettingsToDocument, useAuth } from "../context/useAuth";
import { AppNav } from "./AppNav";

function validateClientPassword(pwd: string): string | null {
  if (pwd.length < 12) return "Nowe hasło musi mieć co najmniej 12 znaków.";
  if (!/[A-Z]/.test(pwd)) return "Nowe hasło musi zawierać co najmniej jedną wielką literę.";
  if (!/[a-z]/.test(pwd)) return "Nowe hasło musi zawierać co najmniej jedną małą literę.";
  if (!/[0-9]/.test(pwd)) return "Nowe hasło musi zawierać co najmniej jedną cyfrę.";
  if (!/[^A-Za-z0-9\s]/.test(pwd)) return "Nowe hasło musi zawierać co najmniej jeden znak specjalny.";
  return null;
}

function triStateToString(val: boolean | null | undefined): string {
  if (val === true) return "true";
  if (val === false) return "false";
  return "system";
}

function stringToTriState(val: string): boolean | null {
  if (val === "true") return true;
  if (val === "false") return false;
  return null;
}

export function SettingsPage() {
  const { token, user, isLoading, refreshUser, updateUserLocal } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);
  const [savingPwd, setSavingPwd] = useState(false);

  const [prefsError, setPrefsError] = useState<string | null>(null);
  const [prefsSuccess, setPrefsSuccess] = useState<string | null>(null);

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }
  if (!user || !token) {
    return null;
  }

  const currentUi: UISettings = user.ui_settings ?? {
    theme: "dark",
    font_size: "normal",
    high_contrast: null,
    reduced_motion: null,
  };

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setPwdError(null);
    setPwdSuccess(null);

    if (!currentPassword || !newPassword || !confirmPassword) {
      setPwdError("Wypełnij wszystkie pola hasła.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdError("Nowe hasło i jego potwierdzenie nie są identyczne.");
      return;
    }
    if (newPassword === currentPassword) {
      setPwdError("Nowe hasło musi różnić się od obecnego hasła.");
      return;
    }
    const policyErr = validateClientPassword(newPassword);
    if (policyErr) {
      setPwdError(policyErr);
      return;
    }

    setSavingPwd(true);
    try {
      await changePasswordRequest(token, currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      await refreshUser();
      setPwdSuccess("Hasło zostało zmienione. Możesz korzystać ze wszystkich funkcji aplikacji.");
    } catch (err: unknown) {
      setPwdError(err instanceof Error ? err.message : "Nie udało się zmienić hasła.");
    } finally {
      setSavingPwd(false);
    }
  }

  async function handlePreferenceChange(patch: Partial<UISettings>) {
    if (!token) return;
    setPrefsError(null);
    setPrefsSuccess(null);

    const optimistic: UISettings = { ...currentUi, ...patch };
    applyUiSettingsToDocument(optimistic);
    updateUserLocal((u) => ({ ...u, ui_settings: optimistic }));

    try {
      const saved = await updateMySettingsRequest(token, patch);
      applyUiSettingsToDocument(saved);
      updateUserLocal((u) => ({ ...u, ui_settings: saved }));
      setPrefsSuccess("Zapisano preferencje dostępności i wyglądu.");
    } catch (err: unknown) {
      setPrefsError(err instanceof Error ? err.message : "Nie udało się zapisać ustawień.");
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
            <h1>Ustawienia użytkownika</h1>
            <p className="cases-subtitle">Zalogowany jako: {user.email}</p>
          </div>
        </div>

        {user.must_change_password && (
          <div className="warning-banner" role="alert">
            <strong>Wymagana zmiana hasła:</strong> Twoje konto wymaga ustawienia nowego hasła
            (minimum 12 znaków) przed przejściem do pozostałych stron aplikacji.
          </div>
        )}

        <div className="settings-grid">
          <section className="cases-table-card" aria-label="Zmień hasło">
            <h2>Zmień hasło</h2>
            <p className="cases-subtitle">
              Wymagania: min. 12 znaków, wielka i mała litera, cyfra oraz znak specjalny.
            </p>
            {pwdSuccess && (
              <div className="status-banner" role="status" aria-live="polite">
                {pwdSuccess}
              </div>
            )}
            {pwdError && (
              <div className="error-banner" role="alert">
                {pwdError}
              </div>
            )}
            <form className="editor-form" onSubmit={handlePasswordSubmit}>
              <div className="form-field">
                <label htmlFor="pwd-current">Obecne hasło</label>
                <input
                  id="pwd-current"
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="pwd-new">Nowe hasło</label>
                <input
                  id="pwd-new"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label htmlFor="pwd-confirm">Potwierdź nowe hasło</label>
                <input
                  id="pwd-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
              <button className="primary-pill-btn" type="submit" disabled={savingPwd}>
                {savingPwd ? "Zapisywanie..." : "Zmień hasło"}
              </button>
            </form>
          </section>

          <section className="cases-table-card" aria-label="Dostępność i wygląd">
            <h2>Dostępność i wygląd</h2>
            <p className="cases-subtitle">
              Preferencje stosują się natychmiast i zapisują się na Twoim koncie.
            </p>
            {prefsSuccess && (
              <div className="status-banner" role="status" aria-live="polite">
                {prefsSuccess}
              </div>
            )}
            {prefsError && (
              <div className="error-banner" role="alert">
                {prefsError}
              </div>
            )}
            <div className="editor-form">
              <div className="form-field">
                <label htmlFor="pref-theme">Motyw</label>
                <select
                  id="pref-theme"
                  disabled={user.must_change_password}
                  value={currentUi.theme}
                  onChange={(e) => void handlePreferenceChange({ theme: e.target.value as UITheme })}
                >
                  <option value="dark">Ciemny — Malinois</option>
                  <option value="light">Jasny</option>
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="pref-font-size">Rozmiar czcionki</label>
                <select
                  id="pref-font-size"
                  disabled={user.must_change_password}
                  value={currentUi.font_size}
                  onChange={(e) =>
                    void handlePreferenceChange({ font_size: e.target.value as UIFontSize })
                  }
                >
                  <option value="small">Mała</option>
                  <option value="normal">Normalna</option>
                  <option value="large">Duża</option>
                  <option value="xl">Bardzo duża</option>
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="pref-high-contrast">Wysoki kontrast</label>
                <select
                  id="pref-high-contrast"
                  disabled={user.must_change_password}
                  value={triStateToString(currentUi.high_contrast)}
                  onChange={(e) =>
                    void handlePreferenceChange({
                      high_contrast: stringToTriState(e.target.value),
                    })
                  }
                >
                  <option value="system">Systemowe</option>
                  <option value="true">Włączony</option>
                  <option value="false">Wyłączony</option>
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="pref-reduced-motion">Ograniczenie animacji</label>
                <select
                  id="pref-reduced-motion"
                  disabled={user.must_change_password}
                  value={triStateToString(currentUi.reduced_motion)}
                  onChange={(e) =>
                    void handlePreferenceChange({
                      reduced_motion: stringToTriState(e.target.value),
                    })
                  }
                >
                  <option value="system">Systemowe</option>
                  <option value="true">Włączone</option>
                  <option value="false">Wyłączone</option>
                </select>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

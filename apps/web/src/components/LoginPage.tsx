import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../api/auth";
import { useAuth } from "../context/useAuth";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type ButtonStatus = "idle" | "loading" | "success" | "error";

export function LoginPage() {
  const { authenticate, commitLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [buttonStatus, setButtonStatus] = useState<ButtonStatus>("idle");
  const [isExiting, setIsExiting] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (buttonStatus === "loading" || buttonStatus === "success") {
      return;
    }

    setError(null);

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError("Wypełnij pola Email oraz Hasło.");
      return;
    }

    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setError("Podaj poprawny adres email.");
      return;
    }

    setButtonStatus("loading");

    try {
      const loginData = await authenticate(trimmedEmail, password);
      setButtonStatus("success");

      const isTestEnv = import.meta.env.MODE === "test";
      const delayMs = isTestEnv ? 50 : 850;
      const exitDelay = isTestEnv ? 20 : 400;

      timeoutRef.current = setTimeout(() => {
        setIsExiting(true);
        timeoutRef.current = setTimeout(() => {
          commitLogin(loginData);
        }, exitDelay);
      }, delayMs);
    } catch (err: unknown) {
      setButtonStatus("error");
      if (err instanceof ApiError && err.status === 401) {
        setError("Niepoprawny login lub hasło");
      } else {
        setError("Błąd połączenia z serwerem. Sprawdź połączenie z internetem.");
      }
      timeoutRef.current = setTimeout(() => {
        setButtonStatus("idle");
      }, 2000);
    }
  }

  return (
    <div className={`login-container ${isExiting ? "page-exit" : ""}`}>
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />

      <h1 className="brand-title">MALINOIS</h1>

      <main className="login-form-wrapper">
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="input-group">
            <label className="input-label" htmlFor="email">
              email
            </label>
            <input
              id="email"
              className="underlined-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>

          <div className="input-group">
            <label className="input-label" htmlFor="password">
              hasło
            </label>
            <input
              id="password"
              className="underlined-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className={`submit-btn state-${buttonStatus}`}
            disabled={buttonStatus === "loading" || buttonStatus === "success"}
          >
            {buttonStatus === "loading" && (
              <svg className="spinner-ring" viewBox="0 0 50 50">
                <circle
                  className="spinner-track"
                  cx="25"
                  cy="25"
                  r="20"
                />
                <circle
                  className="spinner-head"
                  cx="25"
                  cy="25"
                  r="20"
                />
              </svg>
            )}

            {buttonStatus === "success" && (
              <svg className="icon-checkmark" viewBox="0 0 52 52">
                <circle className="circle-pulse" cx="26" cy="26" r="23" />
                <path
                  className="check-path"
                  fill="none"
                  d="M14 27 L23 36 L39 18"
                />
              </svg>
            )}

            {buttonStatus === "error" && (
              <svg className="icon-cross" viewBox="0 0 52 52">
                <circle className="circle-error-pulse" cx="26" cy="26" r="23" />
                <path
                  className="cross-path-1"
                  fill="none"
                  d="M16 16 L36 36"
                />
                <path
                  className="cross-path-2"
                  fill="none"
                  d="M36 16 L16 36"
                />
              </svg>
            )}

            <span className="btn-label">zaloguj</span>
          </button>
        </form>
      </main>
    </div>
  );
}

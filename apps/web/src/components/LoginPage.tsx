import { useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ApiError } from "../api/auth";
import { useAuth } from "../context/useAuth";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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

    setIsSubmitting(true);
    try {
      await login(trimmedEmail, password);
      await navigate({ to: "/" });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Niepoprawny login lub hasło");
      } else {
        setError("Błąd połączenia z serwerem. Sprawdź połączenie z internetem.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Logowanie</h1>
      <form onSubmit={handleSubmit} noValidate>
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>
        <div>
          <label htmlFor="password">Hasło</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Logowanie..." : "Zaloguj"}
        </button>
      </form>
    </main>
  );
}

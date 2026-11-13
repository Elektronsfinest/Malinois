import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ApiError, fetchMeRequest, loginRequest, type User } from "../api/auth";
import { AuthContext } from "./useAuth";

const TOKEN_STORAGE_KEY = "access_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_STORAGE_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  const isLoading = Boolean(token && !user && !authError);

  useEffect(() => {
    if (!token || user) {
      return;
    }

    let cancelled = false;

    fetchMeRequest(token)
      .then((me) => {
        if (!cancelled) {
          setUser(me);
          setAuthError(null);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && err.status === 401) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          setToken(null);
          setUser(null);
          setAuthError(null);
        } else {
          setAuthError("Brak połączenia z serwerem. Sprawdź internet lub uruchomiony backend.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, user]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginRequest(email, password);
    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setAuthError(null);
    setToken(result.access_token);
    setUser(result.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
    setAuthError(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isLoading, authError, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

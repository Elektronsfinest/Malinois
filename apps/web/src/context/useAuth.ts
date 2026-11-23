import { createContext, useContext } from "react";
import type { LoginResponse, User } from "../api/auth";

export interface AuthContextValue {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  authError: string | null;
  login: (email: string, password: string) => Promise<void>;
  authenticate: (email: string, password: string) => Promise<LoginResponse>;
  commitLogin: (data: LoginResponse) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}

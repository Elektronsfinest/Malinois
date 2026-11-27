import { createContext, useContext } from "react";
import type { LoginResponse, UISettings, User } from "../api/auth";

export function applyUiSettingsToDocument(settings?: UISettings) {
  const root = document.documentElement;
  if (!settings) {
    root.dataset.theme = "dark";
    root.dataset.fontSize = "normal";
    delete root.dataset.highContrast;
    delete root.dataset.reducedMotion;
    return;
  }
  root.dataset.theme = settings.theme ?? "dark";
  root.dataset.fontSize = settings.font_size ?? "normal";
  if (settings.high_contrast === null || settings.high_contrast === undefined) {
    delete root.dataset.highContrast;
  } else {
    root.dataset.highContrast = String(settings.high_contrast);
  }
  if (settings.reduced_motion === null || settings.reduced_motion === undefined) {
    delete root.dataset.reducedMotion;
  } else {
    root.dataset.reducedMotion = String(settings.reduced_motion);
  }
}

export interface AuthContextValue {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  authError: string | null;
  login: (email: string, password: string) => Promise<void>;
  authenticate: (email: string, password: string) => Promise<LoginResponse>;
  commitLogin: (data: LoginResponse) => void;
  refreshUser: () => Promise<void>;
  updateUserLocal: (updater: (current: User) => User) => void;
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

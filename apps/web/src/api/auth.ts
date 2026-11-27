export type UserRole = "admin" | "supervisor" | "user";
export type UITheme = "dark" | "light";
export type UIFontSize = "small" | "normal" | "large" | "xl";

export interface UISettings {
  theme: UITheme;
  font_size: UIFontSize;
  high_contrast: boolean | null;
  reduced_motion: boolean | null;
}

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  role: UserRole;
  supervisor_id: number | null;
  must_change_password: boolean;
  ui_settings?: UISettings;
  notification_threshold_days?: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function loginRequest(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response, "Błąd logowania"));
  }

  return (await response.json()) as LoginResponse;
}

export async function fetchMeRequest(token: string): Promise<User> {
  const response = await fetch(`${API_URL}/api/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, "Nieprawidłowy token");
  }

  return (await response.json()) as User;
}

export async function changePasswordRequest(
  token: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const response = await fetch(`${API_URL}/api/me/password`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorDetail(response, "Nie udało się zmienić hasła.")
    );
  }
}

export async function updateMySettingsRequest(
  token: string,
  patch: Partial<UISettings>
): Promise<UISettings> {
  const response = await fetch(`${API_URL}/api/me/settings`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorDetail(response, "Nie udało się zapisać ustawień.")
    );
  }

  return (await response.json()) as UISettings;
}

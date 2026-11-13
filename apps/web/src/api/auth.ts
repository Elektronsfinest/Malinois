export interface User {
  id: number;
  email: string;
  is_active: boolean;
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

export async function loginRequest(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/api/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    let message = "Błąd logowania";
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) {
        message = data.detail;
      }
    } catch {
      message = "Błąd logowania";
    }
    throw new ApiError(response.status, message);
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

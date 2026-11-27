import { ApiError } from "./auth";

export type NotificationUrgency = "upcoming" | "overdue";

export interface NotificationItem {
  case_id: number;
  case_title: string;
  client_name: string;
  assigned_to_email: string;
  deadline: string;
  days_remaining: number;
  urgency: NotificationUrgency;
  version: number;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchNotificationsRequest(token: string): Promise<NotificationItem[]> {
  const res = await fetch(`${API_URL}/api/notifications`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Nie udało się pobrać powiadomień.");
  }
  return (await res.json()) as NotificationItem[];
}

export async function dismissNotificationRequest(token: string, caseId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/notifications/${caseId}/dismiss`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, "Nie udało się odrzucić powiadomienia.");
  }
}

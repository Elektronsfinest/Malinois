import { ApiError } from "./auth";

export interface TeamMemberSummary {
  user_id: number;
  email: string;
  is_active: boolean;
  open_cases: number;
  overdue_cases: number;
  due_soon: number;
}

export interface DashboardSummary {
  notification_threshold_days: number;
  open_cases: number;
  overdue_cases: number;
  due_soon: number;
  closed_this_month: number;
  team_summary: TeamMemberSummary[] | null;
  total_cases: number | null;
  import_last_at: string | null;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchDashboardSummaryRequest(token: string): Promise<DashboardSummary> {
  const res = await fetch(`${API_URL}/api/dashboard/summary`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    let msg = "Nie udało się pobrać podsumowania.";
    try {
      const data = (await res.json()) as { detail?: string };
      if (data.detail) {
        msg = data.detail;
      }
    } catch {
      // ignore
    }
    throw new ApiError(res.status, msg);
  }
  return (await res.json()) as DashboardSummary;
}

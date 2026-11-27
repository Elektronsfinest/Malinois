import { ApiError, type User, type UserRole } from "./auth";

export interface AdminUserCreatePayload {
  email: string;
  password: string;
  role: UserRole;
  supervisor_id: number | null;
}

export interface AdminUserUpdatePayload {
  role?: UserRole;
  supervisor_id?: number | null;
  is_active?: boolean;
  reassign_cases_to?: number | null;
  reassign_subordinates_to?: number | null;
}

export class DeactivationConflictError extends ApiError {
  blockingCaseIds: number[];
  blockingSubordinateIds: number[];

  constructor(message: string, caseIds: number[], subIds: number[]) {
    super(409, message);
    this.blockingCaseIds = caseIds;
    this.blockingSubordinateIds = subIds;
  }
}

export interface AdminAuditLogEntry {
  id: number;
  actor_email: string;
  action: string;
  target_user_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AdminAuditLogListResponse {
  items: AdminAuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function parseErr(res: Response, fallback: string): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string };
    return data.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function fetchAdminUsersRequest(token: string): Promise<User[]> {
  const res = await fetch(`${API_URL}/api/admin/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać użytkowników."));
  }
  return (await res.json()) as User[];
}

export async function createAdminUserRequest(
  token: string,
  payload: AdminUserCreatePayload
): Promise<User> {
  const res = await fetch(`${API_URL}/api/admin/users`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się utworzyć użytkownika."));
  }
  return (await res.json()) as User;
}

export async function updateAdminUserRequest(
  token: string,
  userId: number,
  payload: AdminUserUpdatePayload
): Promise<User> {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (res.status === 409) {
    const data = (await res.json()) as {
      detail?: string;
      blocking_case_ids?: number[];
      blocking_subordinate_ids?: number[];
    };
    throw new DeactivationConflictError(
      data.detail || "Wymagane przepisanie spraw lub podwładnych.",
      data.blocking_case_ids ?? [],
      data.blocking_subordinate_ids ?? []
    );
  }
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się zaktualizować użytkownika."));
  }
  return (await res.json()) as User;
}

export async function resetAdminUserPasswordRequest(
  token: string,
  userId: number
): Promise<string> {
  const res = await fetch(`${API_URL}/api/admin/users/${userId}/reset-password`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się zresetować hasła."));
  }
  const data = (await res.json()) as { temporary_password: string };
  return data.temporary_password;
}

export async function fetchAdminSettingsRequest(
  token: string
): Promise<{ notification_threshold_days: number }> {
  const res = await fetch(`${API_URL}/api/admin/settings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać ustawień."));
  }
  return (await res.json()) as { notification_threshold_days: number };
}

export async function updateAdminSettingsRequest(
  token: string,
  notificationThresholdDays: number
): Promise<{ notification_threshold_days: number }> {
  const res = await fetch(`${API_URL}/api/admin/settings`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ notification_threshold_days: notificationThresholdDays }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się zapisać ustawień."));
  }
  return (await res.json()) as { notification_threshold_days: number };
}

export async function fetchAdminAuditLogRequest(
  token: string,
  action = "",
  page = 1,
  pageSize = 50
): Promise<AdminAuditLogListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (action) {
    params.set("action", action);
  }
  const res = await fetch(`${API_URL}/api/admin/audit-log?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać dziennika audytu."));
  }
  return (await res.json()) as AdminAuditLogListResponse;
}

export interface BackupLogEntry {
  id: number;
  filename: string;
  size_bytes: number;
  backup_type: "automated" | "manual" | "pre_import";
  created_at: string;
}

export async function fetchAdminBackupsRequest(token: string): Promise<BackupLogEntry[]> {
  const res = await fetch(`${API_URL}/api/admin/backups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać listy kopii zapasowych."));
  }
  return (await res.json()) as BackupLogEntry[];
}

export async function triggerAdminBackupRequest(token: string): Promise<BackupLogEntry> {
  const res = await fetch(`${API_URL}/api/admin/backups`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się utworzyć kopii zapasowej."));
  }
  return (await res.json()) as BackupLogEntry;
}

export async function downloadAdminBackupRequest(
  token: string,
  filename: string,
  password: string
): Promise<Blob> {
  const res = await fetch(`${API_URL}/api/admin/backups/${encodeURIComponent(filename)}/download`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać kopii zapasowej."));
  }
  return await res.blob();
}

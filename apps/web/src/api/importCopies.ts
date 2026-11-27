import { ApiError } from "./auth";
import type { CaseStatus } from "./cases";

export type WorkingCopySourceType = "upload" | "snapshot";
export type ConflictResolution = "skip" | "update_existing";

export interface WorkingCopyRow {
  row_index: number;
  case_id: number | null;
  version: number | null;
  case_number: string | null;
  title: string | null;
  client_name: string | null;
  assigned_to_email: string | null;
  deadline: string | null;
  date_filed: string | null;
  status: CaseStatus;
  note: string | null;
  extra_columns: Record<string, string | null>;
  errors: string[];
  warnings: string[];
  conflict: boolean;
  resolution: ConflictResolution | null;
}

export interface WorkingCopySummary {
  id: number;
  source_type: WorkingCopySourceType;
  label: string;
  row_count: number;
  error_count: number;
  conflict_count: number;
  created_at: string;
  expires_at: string;
}

export interface WorkingCopyDetail extends WorkingCopySummary {
  rows: WorkingCopyRow[];
}

export interface WorkingCopyRowPatch {
  row_index: number;
  case_number?: string | null;
  title?: string | null;
  client_name?: string | null;
  assigned_to_email?: string | null;
  deadline?: string | null;
  date_filed?: string | null;
  status?: CaseStatus;
  note?: string | null;
  extra_columns?: Record<string, string | null>;
  resolution?: ConflictResolution | null;
}

export interface WorkingCopyCommitResult {
  created: number;
  updated: number;
  skipped: number;
  conflicts: Array<{ row: number; case_id: number | null; reason: string }>;
  errors: Array<{ row: number; reason: string }>;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function parseErr(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function listWorkingCopiesRequest(token: string): Promise<WorkingCopySummary[]> {
  const res = await fetch(`${API_URL}/api/import/copies`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać kopii roboczych."));
  }
  return (await res.json()) as WorkingCopySummary[];
}

export async function getWorkingCopyRequest(token: string, copyId: number): Promise<WorkingCopyDetail> {
  const res = await fetch(`${API_URL}/api/import/copies/${copyId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać kopii roboczej."));
  }
  return (await res.json()) as WorkingCopyDetail;
}

export async function uploadWorkingCopyRequest(
  token: string,
  file: File,
  defaultAssignedTo: number | null
): Promise<WorkingCopyDetail> {
  const form = new FormData();
  form.append("file", file);
  if (defaultAssignedTo !== null) {
    form.append("default_assigned_to", String(defaultAssignedTo));
  }

  const res = await fetch(`${API_URL}/api/import/copies/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się wgrać pliku Excel."));
  }
  return (await res.json()) as WorkingCopyDetail;
}

export async function createSnapshotCopyRequest(token: string): Promise<WorkingCopyDetail> {
  const res = await fetch(`${API_URL}/api/import/copies/from-cases`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się utworzyć kopii bieżących spraw."));
  }
  return (await res.json()) as WorkingCopyDetail;
}

export async function patchWorkingCopyRequest(
  token: string,
  copyId: number,
  rows: WorkingCopyRowPatch[]
): Promise<WorkingCopyDetail> {
  const res = await fetch(`${API_URL}/api/import/copies/${copyId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ rows }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się zapisać zmian w kopii."));
  }
  return (await res.json()) as WorkingCopyDetail;
}

export async function deleteWorkingCopyRequest(token: string, copyId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/import/copies/${copyId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się usunąć kopii roboczej."));
  }
}

export async function commitWorkingCopyRequest(
  token: string,
  copyId: number
): Promise<WorkingCopyCommitResult> {
  const res = await fetch(`${API_URL}/api/import/copies/${copyId}/commit`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się zatwierdzić kopii roboczej."));
  }
  return (await res.json()) as WorkingCopyCommitResult;
}

export async function downloadWorkingCopyRequest(token: string, copyId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/import/copies/${copyId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać pliku Excel."));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `malinois-copy-${copyId}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

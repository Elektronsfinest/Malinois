import { ApiError, type UserRole } from "./auth";

export type CaseStatus = "open" | "closed";

export interface CaseItem {
  id: number;
  case_number: string | null;
  title: string;
  client_name: string;
  assigned_to: number;
  assigned_to_email: string;
  assigned_to_is_active: boolean;
  deadline: string | null;
  date_filed: string | null;
  status: CaseStatus;
  archived: boolean;
  is_readonly_archive?: boolean;
  version: number;
  extra_fields: Record<string, string | null> | null;
  created_at: string;
  updated_at: string;
}

export interface CaseListResponse {
  items: CaseItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AssignableUser {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface CaseCreatePayload {
  case_number?: string | null;
  title: string;
  client_name: string;
  assigned_to: number;
  deadline?: string | null;
  date_filed?: string | null;
  status?: CaseStatus;
  extra_fields?: Record<string, string | null> | null;
}

export interface CaseUpdatePayload {
  version: number;
  case_number?: string | null;
  title?: string;
  client_name?: string;
  assigned_to?: number;
  deadline?: string | null;
  date_filed?: string | null;
  status?: CaseStatus;
  extra_fields?: Record<string, string | null> | null;
  reason?: string;
}

export class CaseConflictError extends ApiError {
  current: CaseItem;

  constructor(message: string, current: CaseItem) {
    super(409, message);
    this.current = current;
  }
}

export interface CaseQueryFilters {
  q?: string;
  status?: CaseStatus | "";
  assigned_to?: number | null;
  deadline_from?: string;
  deadline_to?: string;
  overdue?: boolean;
  due_soon?: boolean;
  sort?: "deadline_asc" | "deadline_desc" | "updated_at_desc";
}

export interface BulkCaseItemRef {
  id: number;
  version: number;
}

export interface BulkConflictItem {
  case_id: number;
  expected_version: number;
  current_version: number;
}

export class BulkConflictError extends ApiError {
  conflicts: BulkConflictItem[];

  constructor(message: string, conflicts: BulkConflictItem[]) {
    super(409, message);
    this.conflicts = conflicts;
  }
}

export interface BulkCaseResponse {
  success: boolean;
  affected_count: number;
  action: string;
}

export interface CaseReassignResponse {
  success: boolean;
  reassigned_count: number;
  new_assigned_to: number;
  new_assigned_to_email: string;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function parseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function fetchCasesRequest(
  token: string,
  page = 1,
  pageSize = 50,
  archived = false,
  filters?: CaseQueryFilters
): Promise<CaseListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    archived: archived ? "true" : "false",
  });
  if (filters?.q && filters.q.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters?.status) {
    params.set("status", filters.status);
  }
  if (filters?.assigned_to != null) {
    params.set("assigned_to", String(filters.assigned_to));
  }
  if (filters?.deadline_from) {
    params.set("deadline_from", filters.deadline_from);
  }
  if (filters?.deadline_to) {
    params.set("deadline_to", filters.deadline_to);
  }
  if (filters?.overdue) {
    params.set("overdue", "true");
  }
  if (filters?.due_soon) {
    params.set("due_soon", "true");
  }
  if (filters?.sort && filters.sort !== "deadline_asc") {
    params.set("sort", filters.sort);
  }

  const response = await fetch(`${API_URL}/api/cases?${params.toString()}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response, "Nie udało się pobrać spraw."));
  }

  return (await response.json()) as CaseListResponse;
}

export async function bulkCasesRequest(
  token: string,
  payload: {
    items: BulkCaseItemRef[];
    action: "set_status" | "archive" | "restore";
    params?: { status?: CaseStatus };
  }
): Promise<BulkCaseResponse> {
  const response = await fetch(`${API_URL}/api/cases/bulk`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 409) {
    const data = (await response.json()) as {
      detail?: string;
      conflicts?: BulkConflictItem[];
    };
    throw new BulkConflictError(
      data.detail || "Konflikt wersji w operacji zbiorczej.",
      data.conflicts ?? []
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorMessage(response, "Nie udało się wykonać operacji zbiorczej.")
    );
  }
  return (await response.json()) as BulkCaseResponse;
}

export async function reassignCasesRequest(
  token: string,
  payload: {
    items: BulkCaseItemRef[];
    new_assigned_to: number;
    reason?: string;
  }
): Promise<CaseReassignResponse> {
  const response = await fetch(`${API_URL}/api/cases/reassign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 409) {
    const data = (await response.json()) as {
      detail?: string;
      conflicts?: BulkConflictItem[];
    };
    throw new BulkConflictError(
      data.detail || "Konflikt wersji podczas przepisywania.",
      data.conflicts ?? []
    );
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorMessage(response, "Nie udało się przepisać spraw.")
    );
  }
  return (await response.json()) as CaseReassignResponse;
}

export async function archiveCaseRequest(
  token: string,
  caseId: number,
  version: number
): Promise<CaseItem> {
  const response = await fetch(`${API_URL}/api/cases/${caseId}/archive`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ version }),
  });

  if (response.status === 409) {
    const data = (await response.json()) as { detail?: string; current: CaseItem };
    throw new CaseConflictError(data.detail || "Konflikt wersji.", data.current);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response, "Nie udało się zarchiwizować sprawy."));
  }
  return (await response.json()) as CaseItem;
}

export async function restoreCaseRequest(
  token: string,
  caseId: number,
  version: number
): Promise<CaseItem> {
  const response = await fetch(`${API_URL}/api/cases/${caseId}/restore`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ version }),
  });

  if (response.status === 409) {
    const data = (await response.json()) as { detail?: string; current: CaseItem };
    throw new CaseConflictError(data.detail || "Konflikt wersji.", data.current);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response, "Nie udało się przywrócić sprawy."));
  }
  return (await response.json()) as CaseItem;
}

export async function fetchAssignableUsersRequest(token: string): Promise<AssignableUser[]> {
  const response = await fetch(`${API_URL}/api/users/assignable`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorMessage(response, "Nie udało się pobrać listy pracowników.")
    );
  }

  return (await response.json()) as AssignableUser[];
}

export async function createCaseRequest(
  token: string,
  payload: CaseCreatePayload
): Promise<CaseItem> {
  const response = await fetch(`${API_URL}/api/cases`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response, "Nie udało się utworzyć sprawy."));
  }

  return (await response.json()) as CaseItem;
}

export async function updateCaseRequest(
  token: string,
  caseId: number,
  payload: CaseUpdatePayload
): Promise<CaseItem> {
  const response = await fetch(`${API_URL}/api/cases/${caseId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (response.status === 409) {
    const data = (await response.json()) as { detail?: string; current: CaseItem };
    throw new CaseConflictError(
      data.detail || "Konflikt wersji: sprawa została zmodyfikowana przez innego użytkownika.",
      data.current
    );
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorMessage(response, "Nie udało się zapisać zmian."));
  }

  return (await response.json()) as CaseItem;
}

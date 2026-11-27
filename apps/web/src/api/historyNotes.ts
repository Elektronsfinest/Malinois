import { ApiError } from "./auth";

export interface CaseEditLogEntry {
  id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  reason: string | null;
  changed_by_email: string;
  changed_at: string;
}

export interface CaseNoteItem {
  id: number;
  case_id: number | null;
  subject_user_id: number | null;
  subject_email: string | null;
  content: string;
  author_id: number;
  author_email: string;
  created_at: string;
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

export async function fetchCaseHistoryRequest(
  token: string,
  caseId: number,
  limit = 50,
  offset = 0
): Promise<CaseEditLogEntry[]> {
  const res = await fetch(
    `${API_URL}/api/cases/${caseId}/history?limit=${limit}&offset=${offset}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać historii zmian."));
  }
  return (await res.json()) as CaseEditLogEntry[];
}

export async function fetchCaseNotesRequest(
  token: string,
  caseId: number
): Promise<CaseNoteItem[]> {
  const res = await fetch(`${API_URL}/api/cases/${caseId}/notes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać notatek."));
  }
  return (await res.json()) as CaseNoteItem[];
}

export async function createCaseNoteRequest(
  token: string,
  caseId: number,
  content: string,
  subjectUserId: number | null = null
): Promise<CaseNoteItem> {
  const res = await fetch(`${API_URL}/api/cases/${caseId}/notes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content, subject_user_id: subjectUserId }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się dodać notatki."));
  }
  return (await res.json()) as CaseNoteItem;
}

export async function fetchPersonNotesRequest(
  token: string,
  userId: number
): Promise<CaseNoteItem[]> {
  const res = await fetch(`${API_URL}/api/users/${userId}/notes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się pobrać notatek o pracowniku."));
  }
  return (await res.json()) as CaseNoteItem[];
}

export async function createPersonNoteRequest(
  token: string,
  userId: number,
  content: string
): Promise<CaseNoteItem> {
  const res = await fetch(`${API_URL}/api/users/${userId}/notes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się dodać notatki o pracowniku."));
  }
  return (await res.json()) as CaseNoteItem;
}

export async function deleteNoteRequest(token: string, noteId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/notes/${noteId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await parseErr(res, "Nie udało się usunąć notatki."));
  }
}

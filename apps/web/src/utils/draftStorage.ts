const DRAFT_PREFIX = "malinois_draft:";
const DRAFT_OWNER_KEY = "malinois_draft_owner";

export function saveSessionDraft<T>(userEmail: string, draftKey: string, payload: T): void {
  try {
    const normalized = userEmail.trim().toLowerCase();
    sessionStorage.setItem(DRAFT_OWNER_KEY, normalized);
    sessionStorage.setItem(`${DRAFT_PREFIX}${normalized}:${draftKey}`, JSON.stringify(payload));
  } catch {
    // sessionStorage unavailable
  }
}

export function loadSessionDraft<T>(userEmail: string, draftKey: string): T | null {
  try {
    const normalized = userEmail.trim().toLowerCase();
    const raw = sessionStorage.getItem(`${DRAFT_PREFIX}${normalized}:${draftKey}`);
    if (!raw) {
      return null;
    }
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function clearSessionDraft(userEmail: string, draftKey: string): void {
  try {
    const normalized = userEmail.trim().toLowerCase();
    sessionStorage.removeItem(`${DRAFT_PREFIX}${normalized}:${draftKey}`);
  } catch {
    // ignore
  }
}

export function clearAllSessionDrafts(): void {
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const k = sessionStorage.key(i);
      if (k && (k.startsWith(DRAFT_PREFIX) || k === DRAFT_OWNER_KEY)) {
        keysToRemove.push(k);
      }
    }
    for (const k of keysToRemove) {
      sessionStorage.removeItem(k);
    }
  } catch {
    // ignore
  }
}

export function clearDraftsIfDifferentUser(nextUserEmail: string): void {
  try {
    const owner = sessionStorage.getItem(DRAFT_OWNER_KEY);
    if (owner && owner !== nextUserEmail.trim().toLowerCase()) {
      clearAllSessionDrafts();
    }
  } catch {
    // ignore
  }
}

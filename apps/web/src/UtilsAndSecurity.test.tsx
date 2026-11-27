import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { formatPolishDate, getDeadlineUrgency } from "./utils/dates";
import {
  clearAllSessionDrafts,
  clearDraftsIfDifferentUser,
  clearSessionDraft,
  loadSessionDraft,
  saveSessionDraft,
} from "./utils/draftStorage";

describe("Frontend Utilities — dates.ts & draftStorage.ts", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("formatPolishDate konwertuje ISO na DD.MM.YYYY i obsługuje null oraz błędny format", () => {
    expect(formatPolishDate(null)).toBe("Brak terminu");
    expect(formatPolishDate("2027-03-09")).toBe("09.03.2027");
    expect(formatPolishDate("bez-formatu")).toBe("bez-formatu");
  });

  it("getDeadlineUrgency poprawnie klasyfikuje wszystkie progi (zaległe, dziś, 1 dzień, próg, bezpieczne)", () => {
    const today = "2027-05-10";

    expect(getDeadlineUrgency(null, 7, today)).toEqual({
      urgency: "none",
      label: "Brak terminu",
      daysDiff: null,
    });
    expect(getDeadlineUrgency("2027-05-09", 7, today)).toEqual({
      urgency: "overdue",
      label: "ZALEGŁE",
      daysDiff: -1,
    });
    expect(getDeadlineUrgency("2027-05-10", 7, today)).toEqual({
      urgency: "due_soon",
      label: "Dziś",
      daysDiff: 0,
    });
    expect(getDeadlineUrgency("2027-05-11", 7, today)).toEqual({
      urgency: "due_soon",
      label: "Za 1 dzień",
      daysDiff: 1,
    });
    expect(getDeadlineUrgency("2027-05-17", 7, today)).toEqual({
      urgency: "due_soon",
      label: "Za 7 dni",
      daysDiff: 7,
    });
    expect(getDeadlineUrgency("2027-05-18", 7, today)).toEqual({
      urgency: "safe",
      label: "W terminie",
      daysDiff: 8,
    });
  });

  it("draftStorage izoluje szkice między użytkownikami i czyści je przy zmianie konta lub wylogowaniu", () => {
    saveSessionDraft("UserA@Example.com", "case_editor:1", { title: "Szkic A" });
    expect(loadSessionDraft<{ title: string }>("usera@example.com", "case_editor:1")).toEqual({
      title: "Szkic A",
    });
    expect(loadSessionDraft("userb@example.com", "case_editor:1")).toBeNull();

    // Same user does NOT clear drafts
    clearDraftsIfDifferentUser("USERA@example.com");
    expect(loadSessionDraft<{ title: string }>("usera@example.com", "case_editor:1")).toEqual({
      title: "Szkic A",
    });

    // Different user MUST clear drafts immediately
    clearDraftsIfDifferentUser("other@example.com");
    expect(loadSessionDraft("usera@example.com", "case_editor:1")).toBeNull();

    // Explicit clear & clearAll
    saveSessionDraft("usera@example.com", "k1", { v: 1 });
    saveSessionDraft("usera@example.com", "k2", { v: 2 });
    clearSessionDraft("usera@example.com", "k1");
    expect(loadSessionDraft("usera@example.com", "k1")).toBeNull();
    expect(loadSessionDraft("usera@example.com", "k2")).toEqual({ v: 2 });
    clearAllSessionDrafts();
    expect(loadSessionDraft("usera@example.com", "k2")).toBeNull();
  });

  it("XSS safety: złośliwe tagi <script> i <img> w nazwie sprawy są escapowane jako zwykły tekst", async () => {
    localStorage.setItem("access_token", "tok-xss");
    const xssTitle = '<script>window.__xss=1</script><img src=x onerror="alert(1)">';
    const xssClient = '"><svg onload=alert(2)>';

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/me")) {
        return new Response(
          JSON.stringify({
            id: 1,
            email: "trainee@example.com",
            is_active: true,
            role: "user",
            supervisor_id: null,
            must_change_password: false,
            ui_settings: { theme: "dark", font_size: "normal" },
            notification_threshold_days: 7,
          }),
          { status: 200 }
        );
      }
      if (url.endsWith("/api/notifications")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/api/cases")) {
        return new Response(
          JSON.stringify({
            items: [
              {
                id: 99,
                case_number: "XSS-1",
                title: xssTitle,
                client_name: xssClient,
                assigned_to: 1,
                assigned_to_email: "trainee@example.com",
                assigned_to_is_active: true,
                deadline: "2027-06-01",
                date_filed: null,
                status: "open",
                archived: false,
                version: 1,
                extra_fields: null,
                created_at: "2027-01-01T00:00:00Z",
                updated_at: "2027-01-01T00:00:00Z",
              },
            ],
            total: 1,
            page: 1,
            page_size: 50,
          }),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    });

    window.history.pushState({}, "", "/cases");
    const { container } = render(<App />);

    expect(await screen.findByText(xssTitle)).toBeInTheDocument();
    expect(screen.getByText(xssClient)).toBeInTheDocument();
    // Zero injected <script>, <img>, or <svg onload=...> elements in DOM
    expect(container.querySelectorAll("script").length).toBe(0);
    expect(container.querySelectorAll("img").length).toBe(0);
    expect((window as unknown as { __xss?: number }).__xss).toBeUndefined();
  });
});

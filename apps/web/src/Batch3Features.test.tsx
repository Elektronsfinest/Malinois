import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const ADMIN_USER = {
  id: 1,
  email: "admin@example.com",
  is_active: true,
  role: "admin" as const,
  supervisor_id: null,
  must_change_password: false,
  ui_settings: { theme: "dark", font_size: "normal", high_contrast: null, reduced_motion: null },
  notification_threshold_days: 7,
};

const SAMPLE_CASES = [
  {
    id: 10,
    case_number: "E2-010",
    title: "Sprawa Alpha",
    client_name: "Jan Kowalski",
    assigned_to: 1,
    assigned_to_email: "admin@example.com",
    assigned_to_is_active: true,
    deadline: "2026-11-20",
    date_filed: "2026-11-01",
    status: "open",
    archived: false,
    version: 2,
    extra_fields: null,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
  },
  {
    id: 11,
    case_number: "E2-011",
    title: "Sprawa Beta",
    client_name: "Anna Nowak",
    assigned_to: 2,
    assigned_to_email: "trainee@example.com",
    assigned_to_is_active: true,
    deadline: "2026-12-01",
    date_filed: "2026-11-02",
    status: "open",
    archived: false,
    version: 1,
    extra_fields: null,
    created_at: "2026-11-02T10:00:00Z",
    updated_at: "2026-11-02T10:00:00Z",
  },
];

describe("Batch 3 — Dashboard, Search/Filter, Bulk, Reassign, Backups & 401 Draft Recovery", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    localStorage.setItem("access_token", "tok-admin");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("wyświetla Dashboard ze statystykami, tabelą zespołu i ostatnim importem (Spec 014)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/api/me")) {
        return new Response(JSON.stringify(ADMIN_USER), { status: 200 });
      }
      if (url.endsWith("/api/notifications")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/api/dashboard/summary")) {
        return new Response(
          JSON.stringify({
            notification_threshold_days: 7,
            open_cases: 14,
            overdue_cases: 3,
            due_soon: 5,
            closed_this_month: 8,
            total_cases: 22,
            import_last_at: "2026-11-25T10:30:00Z",
            team_summary: [
              {
                user_id: 2,
                email: "trainee@example.com",
                is_active: true,
                open_cases: 6,
                overdue_cases: 2,
                due_soon: 1,
              },
            ],
          }),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    });

    window.history.pushState({}, "", "/");
    render(<App />);

    expect(await screen.findByText("Otwarte sprawy")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getAllByText("Zaległe").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Zbliżający się termin (≤ 7 dni)")).toBeInTheDocument();
    expect(screen.getByText("trainee@example.com")).toBeInTheDocument();
    expect(screen.getByText(/Ostatni import/i)).toBeInTheDocument();
  });

  it("obsługuje zaznaczanie zbiorcze, zmianę statusu i zachowanie szkicu przy 401 (Specs 011, 013, 015)", async () => {
    const user = userEvent.setup();
    let patchAttempts = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/me")) {
        return new Response(JSON.stringify(ADMIN_USER), { status: 200 });
      }
      if (url.endsWith("/api/notifications")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/api/users/assignable")) {
        return new Response(
          JSON.stringify([
            { id: 1, email: "admin@example.com", role: "admin", is_active: true },
            { id: 2, email: "trainee@example.com", role: "user", is_active: true },
          ]),
          { status: 200 }
        );
      }
      if (url.includes("/api/cases/bulk") && method === "POST") {
        return new Response(
          JSON.stringify({ success: true, affected_count: 2, action: "set_status" }),
          { status: 200 }
        );
      }
      if (url.includes("/api/cases/10") && method === "PATCH") {
        patchAttempts += 1;
        if (patchAttempts === 1) {
          return new Response(JSON.stringify({ detail: "Token expired" }), { status: 401 });
        }
        return new Response(
          JSON.stringify({ ...SAMPLE_CASES[0], title: "Zmieniony tytuł po 401", version: 3 }),
          { status: 200 }
        );
      }
      if (url.includes("/api/cases/10/notes") || url.includes("/api/cases/10/history")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/api/login") && method === "POST") {
        return new Response(
          JSON.stringify({
            access_token: "tok-admin-refreshed",
            token_type: "bearer",
            user: ADMIN_USER,
          }),
          { status: 200 }
        );
      }
      if (url.includes("/api/cases")) {
        return new Response(
          JSON.stringify({ items: SAMPLE_CASES, total: 2, page: 1, page_size: 50 }),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    });

    window.history.pushState({}, "", "/cases");
    render(<App />);

    expect(await screen.findByText("Sprawa Alpha")).toBeInTheDocument();

    // Select all -> sticky bulk action bar appears
    await user.click(screen.getByLabelText("Zaznacz wszystkie na tej stronie"));
    expect(screen.getByText("Zaznaczono: 2 spraw")).toBeInTheDocument();

    // Bulk status change
    await user.click(screen.getByRole("button", { name: "Zmień status" }));
    await user.click(screen.getByRole("button", { name: "Zatwierdź" }));
    expect(await screen.findByText("Zaktualizowano 2 spraw")).toBeInTheDocument();

    // Open editor, modify title, trigger 401 -> ReLoginModal preserves draft
    await user.click(screen.getByText("Sprawa Alpha"));
    const titleInput = await screen.findByLabelText("Tytuł sprawy");
    await user.clear(titleInput);
    await user.type(titleInput, "Zmieniony tytuł po 401");
    await user.click(screen.getByRole("button", { name: "Zapisz zmiany" }));

    expect(
      await screen.findByText("Sesja wygasła — zaloguj się ponownie")
    ).toBeInTheDocument();

    await user.type(screen.getByLabelText("Hasło"), "Secret123!");
    await user.click(screen.getByRole("button", { name: "Zaloguj ponownie" }));

    await waitFor(() => {
      expect(
        screen.queryByText("Sesja wygasła — zaloguj się ponownie")
      ).not.toBeInTheDocument();
    });
    expect(screen.getByLabelText("Tytuł sprawy")).toHaveValue("Zmieniony tytuł po 401");
  });

  it("zakładka Kopie zapasowe w /admin tworzy kopię i wymaga hasła przy pobieraniu (Spec 017)", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/me")) {
        return new Response(JSON.stringify(ADMIN_USER), { status: 200 });
      }
      if (url.endsWith("/api/notifications")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/api/admin/users")) {
        return new Response(JSON.stringify([ADMIN_USER]), { status: 200 });
      }
      if (url.endsWith("/api/admin/settings")) {
        return new Response(JSON.stringify({ notification_threshold_days: 7 }), { status: 200 });
      }
      if (url.endsWith("/api/admin/backups") && method === "GET") {
        return new Response(
          JSON.stringify([
            {
              id: 1,
              filename: "malinois_backup_20261125_020000_automated.sqlite.gz",
              size_bytes: 20480,
              backup_type: "automated",
              created_at: "2026-11-25T02:00:00Z",
            },
          ]),
          { status: 200 }
        );
      }
      if (url.endsWith("/api/admin/backups") && method === "POST") {
        return new Response(
          JSON.stringify({
            id: 2,
            filename: "malinois_backup_20261126_074000_manual.sqlite.gz",
            size_bytes: 24576,
            backup_type: "manual",
            created_at: "2026-11-26T07:40:00Z",
          }),
          { status: 201 }
        );
      }
      return new Response(JSON.stringify({}), { status: 200 });
    });

    window.history.pushState({}, "", "/admin");
    render(<App />);

    await user.click(await screen.findByRole("tab", { name: "Kopie zapasowe" }));
    expect(
      await screen.findByText("malinois_backup_20261125_020000_automated.sqlite.gz")
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Utwórz kopię zapasową" }));
    expect(
      await screen.findByText("malinois_backup_20261126_074000_manual.sqlite.gz")
    ).toBeInTheDocument();

    const downloadButtons = screen.getAllByRole("button", { name: "Pobierz" });
    await user.click(downloadButtons[0]);
    expect(await screen.findByText("Potwierdź hasło administratora")).toBeInTheDocument();
  });
});

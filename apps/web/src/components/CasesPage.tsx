import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { ApiError } from "../api/auth";
import {
  archiveCaseRequest,
  BulkConflictError,
  bulkCasesRequest,
  CaseConflictError,
  createCaseRequest,
  fetchAssignableUsersRequest,
  fetchCasesRequest,
  reassignCasesRequest,
  updateCaseRequest,
  type AssignableUser,
  type BulkCaseItemRef,
  type BulkConflictItem,
  type CaseItem,
  type CaseQueryFilters,
  type CaseStatus,
  type CaseUpdatePayload,
} from "../api/cases";
import { useAuth } from "../context/useAuth";
import type { CasesSearchParams } from "../router";
import { formatPolishDate, getDeadlineUrgency, getTodayWarsawIso } from "../utils/dates";
import {
  clearSessionDraft,
  loadSessionDraft,
  saveSessionDraft,
} from "../utils/draftStorage";
import { AppNav } from "./AppNav";
import { CaseEditorExtras } from "./CaseEditorExtras";
import { PersonNotesModal } from "./PersonNotesModal";
import { ReassignModal } from "./ReassignModal";
import { ReLoginModal } from "./ReLoginModal";

interface EditorDraft {
  case_number: string;
  title: string;
  client_name: string;
  assigned_to: number;
  deadline: string;
  date_filed: string;
  status: CaseStatus;
  extra_fields: Record<string, string | null>;
  reason: string;
}

interface CreateDraft {
  case_number: string;
  title: string;
  client_name: string;
  assigned_to: number | "";
  deadline: string;
  date_filed: string;
}

function buildDraft(c: CaseItem): EditorDraft {
  return {
    case_number: c.case_number ?? "",
    title: c.title,
    client_name: c.client_name,
    assigned_to: c.assigned_to,
    deadline: c.deadline ?? "",
    date_filed: c.date_filed ?? "",
    status: c.status,
    extra_fields: c.extra_fields ? { ...c.extra_fields } : {},
    reason: "",
  };
}

export function CasesPage() {
  const { token, user, isLoading } = useAuth();
  const search = useSearch({ from: "/cases" });
  const navigate = useNavigate({ from: "/cases" });

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [reloadTick, setReloadTick] = useState(0);
  const pageSize = 50;
  const [loadingCases, setLoadingCases] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Search input (debounced 300ms -> URL search param q)
  const [searchInput, setSearchInput] = useState(search.q ?? "");

  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);

  // Inline Editor state
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [draft, setDraft] = useState<EditorDraft | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [savingEditor, setSavingEditor] = useState(false);

  // 409 Conflict state (single case)
  const [conflict, setConflict] = useState<{
    caseId: number;
    pendingPayload: CaseUpdatePayload;
    current: CaseItem;
  } | null>(null);

  // Spec 015 Bulk selection & action state
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkConflicts, setBulkConflicts] = useState<BulkConflictItem[] | null>(null);
  const [bulkConfirm, setBulkConfirm] = useState<
    { kind: "set_status"; status: CaseStatus } | { kind: "archive" } | null
  >(null);

  // Spec 016 Reassignment modal state (single or bulk)
  const [reassignTargets, setReassignTargets] = useState<BulkCaseItemRef[] | null>(null);
  const [reassignBusy, setReassignBusy] = useState(false);
  const [reassignError, setReassignError] = useState<string | null>(null);

  // Spec 011 401 Session-Expiry re-login modal state
  const [reloginContext, setReloginContext] = useState<{
    expectedEmail: string;
    draftKey: string;
    kind: "editor" | "create";
    caseId?: number;
  } | null>(null);

  // Create Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showPersonNotes, setShowPersonNotes] = useState(false);
  const [archiveConfirmCase, setArchiveConfirmCase] = useState<CaseItem | null>(null);
  const [createCaseNumber, setCreateCaseNumber] = useState("");
  const [createTitle, setCreateTitle] = useState("");
  const [createClientName, setCreateClientName] = useState("");
  const [createAssignedTo, setCreateAssignedTo] = useState<number | "">("");
  const [createDeadline, setCreateDeadline] = useState("");
  const [createDateFiled, setCreateDateFiled] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const isAdmin = user?.role === "admin";
  const isSupervisorOrAdmin = user?.role === "admin" || user?.role === "supervisor";
  const todayIso = getTodayWarsawIso();

  function updateSearchParams(patch: Partial<CasesSearchParams>) {
    const next: CasesSearchParams = { ...search, ...patch };
    const cleaned: CasesSearchParams = {};
    if (next.q && next.q.trim()) cleaned.q = next.q.trim();
    if (next.status) cleaned.status = next.status;
    if (next.assigned_to) cleaned.assigned_to = next.assigned_to;
    if (next.deadline_from) cleaned.deadline_from = next.deadline_from;
    if (next.deadline_to) cleaned.deadline_to = next.deadline_to;
    if (next.overdue) cleaned.overdue = true;
    if (next.due_soon) cleaned.due_soon = true;
    if (next.sort && next.sort !== "deadline_asc") cleaned.sort = next.sort;
    setPage(1);
    void navigate({ search: cleaned });
  }

  function clearAllFilters() {
    setSearchInput("");
    setPage(1);
    void navigate({ search: {} });
  }

  // Debounce searchInput -> URL param q
  useEffect(() => {
    const currentQ = search.q ?? "";
    if (searchInput.trim() === currentQ) {
      return;
    }
    const timer = window.setTimeout(() => {
      updateSearchParams({ q: searchInput.trim() || undefined });
    }, 300);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  useEffect(() => {
    if (!token || !user) {
      return;
    }
    let cancelled = false;

    const filters: CaseQueryFilters = {
      q: search.q,
      status: search.status,
      assigned_to: search.assigned_to,
      deadline_from: search.deadline_from,
      deadline_to: search.deadline_to,
      overdue: search.overdue,
      due_soon: search.due_soon,
      sort: search.sort,
    };

    fetchCasesRequest(token, page, pageSize, false, filters)
      .then((data) => {
        if (!cancelled) {
          setCases(data.items);
          setTotal(data.total);
          setSelectedIds([]);
          setPageError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setPageError(err instanceof Error ? err.message : "Nie udało się pobrać listy spraw.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingCases(false);
        }
      });

    if (user.role === "admin" || user.role === "supervisor") {
      fetchAssignableUsersRequest(token)
        .then((users) => {
          if (!cancelled) {
            setAssignableUsers(users);
            setCreateAssignedTo((prev) => (prev === "" && users.length > 0 ? users[0].id : prev));
          }
        })
        .catch(() => {
          // Handled gracefully if unavailable
        });
    }

    return () => {
      cancelled = true;
    };
  }, [
    token,
    user,
    page,
    reloadTick,
    search.q,
    search.status,
    search.assigned_to,
    search.deadline_from,
    search.deadline_to,
    search.overdue,
    search.due_soon,
    search.sort,
  ]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (conflict) {
          setConflict(null);
        } else if (reassignTargets) {
          setReassignTargets(null);
        } else if (bulkConfirm) {
          setBulkConfirm(null);
        } else if (showCreateModal) {
          setShowCreateModal(false);
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [conflict, reassignTargets, bulkConfirm, showCreateModal]);

  function openEditor(c: CaseItem) {
    setSelectedCase(c);
    setDraft(buildDraft(c));
    setEditorError(null);
  }

  function closeEditor() {
    setSelectedCase(null);
    setDraft(null);
    setEditorError(null);
  }

  function toggleRowSelection(caseId: number) {
    setSelectedIds((prev) =>
      prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]
    );
  }

  function toggleSelectAll() {
    if (cases.length > 0 && selectedIds.length === cases.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(cases.map((c) => c.id));
    }
  }

  async function executeArchive(c: CaseItem) {
    if (!token) {
      return;
    }
    setArchiveConfirmCase(null);
    setStatusMessage(null);
    setPageError(null);
    try {
      await archiveCaseRequest(token, c.id, c.version);
      setCases((prev) => prev.filter((item) => item.id !== c.id));
      setSelectedIds((prev) => prev.filter((id) => id !== c.id));
      setTotal((t) => Math.max(0, t - 1));
      if (selectedCase?.id === c.id) {
        closeEditor();
      }
      setStatusMessage(`Zarchiwizowano sprawę „${c.title}”.`);
    } catch (err: unknown) {
      if (err instanceof CaseConflictError) {
        setConflict({
          caseId: c.id,
          pendingPayload: { version: c.version },
          current: err.current,
        });
      } else {
        setPageError(err instanceof Error ? err.message : "Nie udało się zarchiwizować sprawy.");
      }
    }
  }

  function handleArchiveClick(c: CaseItem) {
    if (c.status === "open") {
      setArchiveConfirmCase(c);
    } else {
      void executeArchive(c);
    }
  }

  async function handleToggleClosed(c: CaseItem) {
    if (!token) {
      return;
    }
    const nextStatus: CaseStatus = c.status === "closed" ? "open" : "closed";
    const payload: CaseUpdatePayload = { version: c.version, status: nextStatus };
    setStatusMessage(null);
    setPageError(null);
    try {
      const updated = await updateCaseRequest(token, c.id, payload);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedCase?.id === updated.id) {
        setSelectedCase(updated);
        setDraft(buildDraft(updated));
      }
      setStatusMessage(
        nextStatus === "closed"
          ? `Sprawa „${updated.title}” została oznaczona jako zakończona.`
          : `Sprawa „${updated.title}” została ponownie otwarta.`
      );
    } catch (err: unknown) {
      if (err instanceof CaseConflictError) {
        setConflict({ caseId: c.id, pendingPayload: payload, current: err.current });
      } else {
        setPageError(err instanceof Error ? err.message : "Nie udało się zaktualizować statusu.");
      }
    }
  }

  async function handleEditorSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !user || !selectedCase || !draft) {
      return;
    }
    setEditorError(null);
    setStatusMessage(null);

    if (!draft.title.trim() || !draft.client_name.trim()) {
      setEditorError("Tytuł sprawy oraz nazwa klienta są wymagane.");
      return;
    }

    const deadlineChanged = isAdmin && (draft.deadline || null) !== selectedCase.deadline;
    const dateFiledChanged = isAdmin && (draft.date_filed || null) !== selectedCase.date_filed;
    if ((deadlineChanged || dateFiledChanged) && !draft.reason.trim()) {
      setEditorError("Zmiana daty wymaga podania powodu (Powód zmiany daty).");
      return;
    }

    const payload: CaseUpdatePayload = {
      version: selectedCase.version,
      title: draft.title.trim(),
      client_name: draft.client_name.trim(),
      status: draft.status,
      extra_fields:
        Object.keys(draft.extra_fields).length > 0
          ? draft.extra_fields
          : selectedCase.extra_fields,
    };

    if (isAdmin) {
      payload.case_number = draft.case_number.trim() || null;
      payload.assigned_to = draft.assigned_to;
      payload.deadline = draft.deadline || null;
      payload.date_filed = draft.date_filed || null;
      if (deadlineChanged || dateFiledChanged) {
        payload.reason = draft.reason.trim();
      }
    }

    setSavingEditor(true);
    try {
      const updated = await updateCaseRequest(token, selectedCase.id, payload);
      clearSessionDraft(user.email, `case_editor:${selectedCase.id}`);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedCase(updated);
      setDraft(buildDraft(updated));
      setStatusMessage("Zapisano zmiany w sprawie.");
    } catch (err: unknown) {
      if (err instanceof CaseConflictError) {
        setConflict({ caseId: selectedCase.id, pendingPayload: payload, current: err.current });
      } else if (err instanceof ApiError && err.status === 401) {
        const draftKey = `case_editor:${selectedCase.id}`;
        saveSessionDraft(user.email, draftKey, draft);
        setReloginContext({
          expectedEmail: user.email,
          draftKey,
          kind: "editor",
          caseId: selectedCase.id,
        });
      } else if (err instanceof ApiError) {
        setEditorError(err.message);
      } else {
        setEditorError("Nie udało się zapisać zmian.");
      }
    } finally {
      setSavingEditor(false);
    }
  }

  async function handleConflictOverwrite() {
    if (!token || !conflict) {
      return;
    }
    const retryPayload: CaseUpdatePayload = {
      ...conflict.pendingPayload,
      version: conflict.current.version,
    };
    try {
      const updated = await updateCaseRequest(token, conflict.caseId, retryPayload);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (selectedCase?.id === updated.id) {
        setSelectedCase(updated);
        setDraft(buildDraft(updated));
      }
      setConflict(null);
      setStatusMessage("Nadpisano sprawę Twoją wersją zmian.");
    } catch (err: unknown) {
      if (err instanceof CaseConflictError) {
        setConflict({
          caseId: conflict.caseId,
          pendingPayload: retryPayload,
          current: err.current,
        });
      } else {
        setEditorError(err instanceof Error ? err.message : "Nie udało się nadpisać zmian.");
        setConflict(null);
      }
    }
  }

  function handleConflictDiscard() {
    if (!conflict) {
      return;
    }
    setCases((prev) =>
      prev.map((item) => (item.id === conflict.current.id ? conflict.current : item))
    );
    if (selectedCase?.id === conflict.current.id) {
      setSelectedCase(conflict.current);
      setDraft(buildDraft(conflict.current));
    }
    setConflict(null);
    setStatusMessage("Odrzucono Twoje zmiany i wczytano najnowszą wersję z serwera.");
  }

  async function handleCreateSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token || !user) {
      return;
    }
    setCreateError(null);

    if (!createTitle.trim() || !createClientName.trim() || createAssignedTo === "") {
      setCreateError("Wypełnij tytuł, nazwę klienta oraz przypisanego pracownika.");
      return;
    }

    setCreating(true);
    try {
      const created = await createCaseRequest(token, {
        case_number: isAdmin ? createCaseNumber.trim() || null : null,
        title: createTitle.trim(),
        client_name: createClientName.trim(),
        assigned_to: Number(createAssignedTo),
        deadline: isAdmin ? createDeadline || null : null,
        date_filed: isAdmin ? createDateFiled || null : null,
      });
      clearSessionDraft(user.email, "case_create");
      setCases((prev) => [created, ...prev]);
      setTotal((t) => t + 1);
      setShowCreateModal(false);
      setCreateCaseNumber("");
      setCreateTitle("");
      setCreateClientName("");
      setCreateDeadline("");
      setCreateDateFiled("");
      setStatusMessage(`Utworzono sprawę „${created.title}”.`);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        const payload: CreateDraft = {
          case_number: createCaseNumber,
          title: createTitle,
          client_name: createClientName,
          assigned_to: createAssignedTo,
          deadline: createDeadline,
          date_filed: createDateFiled,
        };
        saveSessionDraft(user.email, "case_create", payload);
        setReloginContext({
          expectedEmail: user.email,
          draftKey: "case_create",
          kind: "create",
        });
      } else {
        setCreateError(err instanceof Error ? err.message : "Nie udało się utworzyć sprawy.");
      }
    } finally {
      setCreating(false);
    }
  }

  async function executeBulkAction() {
    if (!token || !bulkConfirm || selectedIds.length === 0) {
      return;
    }
    const items = cases
      .filter((c) => selectedIds.includes(c.id))
      .map((c) => ({ id: c.id, version: c.version }));
    setBulkBusy(true);
    setPageError(null);
    setStatusMessage(null);
    setBulkConflicts(null);
    try {
      const res =
        bulkConfirm.kind === "set_status"
          ? await bulkCasesRequest(token, {
              items,
              action: "set_status",
              params: { status: bulkConfirm.status },
            })
          : await bulkCasesRequest(token, { items, action: "archive" });
      setBulkConfirm(null);
      setSelectedIds([]);
      setReloadTick((t) => t + 1);
      setStatusMessage(`Zaktualizowano ${res.affected_count} spraw`);
    } catch (err: unknown) {
      setBulkConfirm(null);
      if (err instanceof BulkConflictError) {
        setBulkConflicts(err.conflicts);
      } else {
        setPageError(
          err instanceof Error ? err.message : "Nie udało się wykonać operacji zbiorczej."
        );
      }
    } finally {
      setBulkBusy(false);
    }
  }

  async function handleConfirmReassign(newAssignedTo: number, reason: string) {
    if (!token || !reassignTargets || reassignTargets.length === 0) {
      return;
    }
    setReassignBusy(true);
    setReassignError(null);
    setBulkConflicts(null);
    try {
      const res = await reassignCasesRequest(token, {
        items: reassignTargets,
        new_assigned_to: newAssignedTo,
        reason: reason || undefined,
      });
      setReassignTargets(null);
      setSelectedIds([]);
      if (selectedCase && reassignTargets.some((t) => t.id === selectedCase.id)) {
        closeEditor();
      }
      setReloadTick((t) => t + 1);
      setStatusMessage(
        `Przepisano ${res.reassigned_count} spraw na ${res.new_assigned_to_email}.`
      );
    } catch (err: unknown) {
      if (err instanceof BulkConflictError) {
        setReassignTargets(null);
        setBulkConflicts(err.conflicts);
      } else {
        setReassignError(
          err instanceof Error ? err.message : "Nie udało się przepisać spraw."
        );
      }
    } finally {
      setReassignBusy(false);
    }
  }

  function handleReloginSuccess(sameUser: boolean) {
    if (!reloginContext) {
      return;
    }
    if (sameUser) {
      if (reloginContext.kind === "editor") {
        const restored = loadSessionDraft<EditorDraft>(
          reloginContext.expectedEmail,
          reloginContext.draftKey
        );
        if (restored) {
          setDraft(restored);
        }
      } else if (reloginContext.kind === "create") {
        const restored = loadSessionDraft<CreateDraft>(
          reloginContext.expectedEmail,
          reloginContext.draftKey
        );
        if (restored) {
          setCreateCaseNumber(restored.case_number);
          setCreateTitle(restored.title);
          setCreateClientName(restored.client_name);
          setCreateAssignedTo(restored.assigned_to);
          setCreateDeadline(restored.deadline);
          setCreateDateFiled(restored.date_filed);
        }
      }
      setStatusMessage("Sesja przywrócona — Twoje niezapisane zmiany zostały zachowane.");
    } else {
      closeEditor();
      setShowCreateModal(false);
    }
    setReloginContext(null);
  }

  if (isLoading) {
    return <p>Ładowanie...</p>;
  }

  if (!user) {
    return null;
  }

  const showPastDeadlineWarning = Boolean(isAdmin && createDeadline && createDeadline < todayIso);
  const editorDateChanged = Boolean(
    isAdmin &&
      selectedCase &&
      draft &&
      ((draft.deadline || null) !== selectedCase.deadline ||
        (draft.date_filed || null) !== selectedCase.date_filed)
  );
  const allSelected = cases.length > 0 && selectedIds.length === cases.length;

  const activeChips: { key: string; label: string; onRemove: () => void }[] = [];
  if (search.q) {
    activeChips.push({
      key: "q",
      label: `Szukaj: "${search.q}"`,
      onRemove: () => {
        setSearchInput("");
        updateSearchParams({ q: undefined });
      },
    });
  }
  if (search.status) {
    activeChips.push({
      key: "status",
      label: `Status: ${search.status === "open" ? "Otwarta" : "Zamknięta"}`,
      onRemove: () => updateSearchParams({ status: undefined }),
    });
  }
  if (search.assigned_to) {
    const u = assignableUsers.find((a) => a.id === search.assigned_to);
    activeChips.push({
      key: "assigned_to",
      label: `Pracownik: ${u ? u.email : `#${search.assigned_to}`}`,
      onRemove: () => updateSearchParams({ assigned_to: undefined }),
    });
  }
  if (search.deadline_from) {
    activeChips.push({
      key: "deadline_from",
      label: `Termin od: ${search.deadline_from}`,
      onRemove: () => updateSearchParams({ deadline_from: undefined }),
    });
  }
  if (search.deadline_to) {
    activeChips.push({
      key: "deadline_to",
      label: `Termin do: ${search.deadline_to}`,
      onRemove: () => updateSearchParams({ deadline_to: undefined }),
    });
  }
  if (search.overdue) {
    activeChips.push({
      key: "overdue",
      label: "Zaległe",
      onRemove: () => updateSearchParams({ overdue: undefined }),
    });
  }
  if (search.due_soon) {
    activeChips.push({
      key: "due_soon",
      label: "Zbliżający się termin",
      onRemove: () => updateSearchParams({ due_soon: undefined }),
    });
  }

  return (
    <div className="app-shell">
      <div className="glow-orb glow-orb-1" />
      <div className="glow-orb glow-orb-2" />
      <AppNav />

      <main className="cases-main" id="main-content">
        <div className="cases-header">
          <div>
            <h1>Sprawy</h1>
            <p className="cases-subtitle">Łącznie aktywnych spraw: {total}</p>
          </div>
          <div className="cases-header-actions">
            <button
              className="secondary-btn"
              type="button"
              onClick={() => setShowPersonNotes(true)}
            >
              {isSupervisorOrAdmin ? "Notatki o pracownikach" : "Moje notatki"}
            </button>
            <Link className="secondary-btn nav-button-link" to="/import">
              Import / Edytor pliku
            </Link>
            {isSupervisorOrAdmin && (
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => {
                  setCreateError(null);
                  setShowCreateModal(true);
                }}
              >
                Nowa sprawa
              </button>
            )}
          </div>
        </div>

        {/* Spec 013: Search & Filter bar */}
        <section className="filter-bar-card" aria-label="Wyszukiwanie i filtrowanie spraw">
          <div className="filter-bar-row">
            <div className="filter-field filter-field-search">
              <label htmlFor="cases-search-q">Szukaj (numer, tytuł, klient)</label>
              <input
                id="cases-search-q"
                type="search"
                placeholder="Wpisz numer sprawy, tytuł lub klienta..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>

            <div className="filter-field">
              <label htmlFor="cases-filter-status">Status</label>
              <select
                id="cases-filter-status"
                value={search.status ?? ""}
                onChange={(e) =>
                  updateSearchParams({
                    status: (e.target.value as CaseStatus) || undefined,
                  })
                }
              >
                <option value="">Wszystkie</option>
                <option value="open">Otwarta</option>
                <option value="closed">Zamknięta</option>
              </select>
            </div>

            {isSupervisorOrAdmin && (
              <div className="filter-field">
                <label htmlFor="cases-filter-assignee">Pracownik</label>
                <select
                  id="cases-filter-assignee"
                  value={search.assigned_to ?? ""}
                  onChange={(e) =>
                    updateSearchParams({
                      assigned_to: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                >
                  <option value="">Wszyscy</option>
                  {assignableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email}
                      {u.is_active ? "" : " (nieaktywny)"}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="filter-field">
              <label htmlFor="cases-filter-from">Termin od</label>
              <input
                id="cases-filter-from"
                type="date"
                value={search.deadline_from ?? ""}
                onChange={(e) =>
                  updateSearchParams({ deadline_from: e.target.value || undefined })
                }
              />
            </div>

            <div className="filter-field">
              <label htmlFor="cases-filter-to">Termin do</label>
              <input
                id="cases-filter-to"
                type="date"
                value={search.deadline_to ?? ""}
                onChange={(e) =>
                  updateSearchParams({ deadline_to: e.target.value || undefined })
                }
              />
            </div>

            <div className="filter-field">
              <label htmlFor="cases-filter-sort">Sortowanie</label>
              <select
                id="cases-filter-sort"
                value={search.sort ?? "deadline_asc"}
                onChange={(e) =>
                  updateSearchParams({
                    sort: e.target.value as CasesSearchParams["sort"],
                  })
                }
              >
                <option value="deadline_asc">Termin rosnąco</option>
                <option value="deadline_desc">Termin malejąco</option>
                <option value="updated_at_desc">Ostatnio zmienione</option>
              </select>
            </div>
          </div>

          <div className="filter-toggles">
            <button
              type="button"
              className={`filter-toggle-btn${search.overdue ? " active" : ""}`}
              aria-pressed={Boolean(search.overdue)}
              onClick={() => updateSearchParams({ overdue: search.overdue ? undefined : true })}
            >
              Zaległe
            </button>
            <button
              type="button"
              className={`filter-toggle-btn${search.due_soon ? " active" : ""}`}
              aria-pressed={Boolean(search.due_soon)}
              onClick={() => updateSearchParams({ due_soon: search.due_soon ? undefined : true })}
            >
              Zbliżający się termin
            </button>
          </div>

          {activeChips.length > 0 && (
            <div className="filter-chips-row" aria-label="Aktywne filtry">
              {activeChips.map((chip) => (
                <span key={chip.key} className="filter-chip">
                  {chip.label}
                  <button
                    type="button"
                    aria-label={`Usuń filtr ${chip.label}`}
                    onClick={chip.onRemove}
                  >
                    ×
                  </button>
                </span>
              ))}
              <button className="secondary-btn" type="button" onClick={clearAllFilters}>
                Wyczyść filtry
              </button>
            </div>
          )}
        </section>

        {statusMessage && (
          <div className="status-banner" role="status" aria-live="polite">
            {statusMessage}
          </div>
        )}

        {pageError && (
          <div className="error-banner" role="alert">
            {pageError}
          </div>
        )}

        {bulkConflicts && (
          <div className="error-banner" role="alert">
            <p>
              Konflikt wersji dla spraw:{" "}
              {bulkConflicts
                .map((c) => `#${c.case_id} (v${c.expected_version} → v${c.current_version})`)
                .join(", ")}
              .
            </p>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => {
                setBulkConflicts(null);
                setReloadTick((t) => t + 1);
              }}
            >
              Odśwież tabelę
            </button>
          </div>
        )}

        <div className="cases-layout">
          <section className="cases-table-card" aria-label="Lista spraw">
            {loadingCases ? (
              <p className="cases-empty">Wczytywanie spraw...</p>
            ) : cases.length === 0 ? (
              <p className="cases-empty">Brak aktywnych spraw w Twoim zakresie.</p>
            ) : (
              <div className="table-scroll">
                <table className="cases-table">
                  <thead>
                    <tr>
                      <th scope="col" className="checkbox-col">
                        <input
                          type="checkbox"
                          aria-label="Zaznacz wszystkie na tej stronie"
                          checked={allSelected}
                          disabled={bulkBusy}
                          onChange={toggleSelectAll}
                        />
                      </th>
                      <th scope="col">Numer sprawy</th>
                      <th scope="col">Tytuł</th>
                      <th scope="col">Klient</th>
                      {isSupervisorOrAdmin && <th scope="col">Przypisany</th>}
                      <th scope="col">Termin realizacji</th>
                      <th scope="col">Status</th>
                      <th scope="col">Akcje</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => {
                      const urgencyInfo = getDeadlineUrgency(
                        c.deadline,
                        user.notification_threshold_days ?? 7,
                        todayIso
                      );
                      const isSelected = selectedCase?.id === c.id;
                      return (
                        <tr
                          key={c.id}
                          className={`case-row case-row-${urgencyInfo.urgency}${isSelected ? " case-row-selected" : ""}`}
                          onClick={() => openEditor(c)}
                        >
                          <td
                            className="checkbox-col"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <input
                              type="checkbox"
                              aria-label={`Zaznacz sprawę ${c.title}`}
                              checked={selectedIds.includes(c.id)}
                              disabled={bulkBusy}
                              onChange={() => toggleRowSelection(c.id)}
                            />
                          </td>
                          <td>{c.case_number ?? "—"}</td>
                          <td className="case-title-cell">{c.title}</td>
                          <td>{c.client_name}</td>
                          {isSupervisorOrAdmin && (
                            <td>
                              {c.assigned_to_email}
                              {!c.assigned_to_is_active && (
                                <span className="inactive-tag"> (nieaktywny)</span>
                              )}
                            </td>
                          )}
                          <td>
                            <div className="deadline-cell">
                              <span>{formatPolishDate(c.deadline)}</span>
                              <span className={`urgency-badge urgency-${urgencyInfo.urgency}`}>
                                {urgencyInfo.label}
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className={`status-pill status-${c.status}`}>
                              {c.status === "closed" ? "Zamknięta" : "Otwarta"}
                            </span>
                          </td>
                          <td onClick={(e) => e.stopPropagation()}>
                            <div className="row-actions">
                              <button
                                className="row-btn"
                                type="button"
                                onClick={() => openEditor(c)}
                              >
                                Edytuj
                              </button>
                              <button
                                className="row-btn row-btn-toggle"
                                type="button"
                                aria-label={`Zakończono: ${c.title}`}
                                onClick={() => void handleToggleClosed(c)}
                              >
                                {c.status === "closed" ? "Otwórz" : "Zakończono"}
                              </button>
                              <button
                                className="row-btn"
                                type="button"
                                aria-label={`Archiwizuj: ${c.title}`}
                                onClick={() => handleArchiveClick(c)}
                              >
                                Archiwizuj
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {total > pageSize && (
              <div className="pagination-bar" aria-label="Stronicowanie spraw">
                <span>
                  Strona {page} z {Math.max(1, Math.ceil(total / pageSize))} (wyświetlono{" "}
                  {cases.length} z {total})
                </span>
                <div className="pagination-buttons">
                  <button
                    className="secondary-btn"
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Poprzednia
                  </button>
                  <button
                    className="secondary-btn"
                    type="button"
                    disabled={page * pageSize >= total}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Następna
                  </button>
                </div>
              </div>
            )}
          </section>

          {selectedCase && draft && (
            <aside className="case-editor-panel" aria-label="Edytor wstępny">
              <div className="editor-header">
                <h2>Edytor wstępny</h2>
                <button
                  className="icon-close-btn"
                  type="button"
                  aria-label="Zamknij edytor"
                  onClick={closeEditor}
                >
                  ✕
                </button>
              </div>
              <p className="editor-meta">
                ID #{selectedCase.id} · Wersja {selectedCase.version}
              </p>

              {editorError && (
                <div className="error-banner" role="alert">
                  {editorError}
                </div>
              )}

              <form className="editor-form" onSubmit={handleEditorSubmit}>
                {isAdmin && (
                  <div className="form-field">
                    <label htmlFor="edit-case-number">Numer sprawy (E2)</label>
                    <input
                      id="edit-case-number"
                      type="text"
                      value={draft.case_number}
                      onChange={(e) => setDraft({ ...draft, case_number: e.target.value })}
                    />
                  </div>
                )}

                <div className="form-field">
                  <label htmlFor="edit-title">Tytuł sprawy</label>
                  <input
                    id="edit-title"
                    type="text"
                    required
                    value={draft.title}
                    onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="edit-client">Klient</label>
                  <input
                    id="edit-client"
                    type="text"
                    required
                    value={draft.client_name}
                    onChange={(e) => setDraft({ ...draft, client_name: e.target.value })}
                  />
                </div>

                <div className="form-field">
                  <label htmlFor="edit-status">Status</label>
                  <select
                    id="edit-status"
                    value={draft.status}
                    onChange={(e) => setDraft({ ...draft, status: e.target.value as CaseStatus })}
                  >
                    <option value="open">Otwarta</option>
                    <option value="closed">Zamknięta</option>
                  </select>
                </div>

                {isAdmin && (
                  <>
                    <div className="form-field">
                      <label htmlFor="edit-assigned-to">Przypisany pracownik</label>
                      <select
                        id="edit-assigned-to"
                        value={draft.assigned_to}
                        onChange={(e) =>
                          setDraft({ ...draft, assigned_to: Number(e.target.value) })
                        }
                      >
                        {assignableUsers.map((u) => (
                          <option key={u.id} value={u.id}>
                            {u.email}
                            {u.is_active ? "" : " (nieaktywny)"}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-field">
                      <label htmlFor="edit-deadline">Termin realizacji</label>
                      <input
                        id="edit-deadline"
                        type="date"
                        value={draft.deadline}
                        onChange={(e) => setDraft({ ...draft, deadline: e.target.value })}
                      />
                    </div>

                    <div className="form-field">
                      <label htmlFor="edit-date-filed">Data wpływu</label>
                      <input
                        id="edit-date-filed"
                        type="date"
                        value={draft.date_filed}
                        onChange={(e) => setDraft({ ...draft, date_filed: e.target.value })}
                      />
                    </div>

                    {editorDateChanged && (
                      <div className="form-field">
                        <label htmlFor="edit-date-reason">Powód zmiany daty *</label>
                        <input
                          id="edit-date-reason"
                          type="text"
                          required
                          maxLength={500}
                          placeholder="np. Korekta pomyłki pisarskiej"
                          value={draft.reason}
                          onChange={(e) => setDraft({ ...draft, reason: e.target.value })}
                        />
                      </div>
                    )}
                  </>
                )}

                {Object.keys(draft.extra_fields).length > 0 && (
                  <fieldset className="extra-fields-group">
                    <legend>Dodatkowe pola ZUS</legend>
                    {Object.entries(draft.extra_fields).map(([key, val]) => (
                      <div className="form-field" key={key}>
                        <label htmlFor={`extra-${key}`}>{key}</label>
                        <input
                          id={`extra-${key}`}
                          type="text"
                          value={val ?? ""}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              extra_fields: { ...draft.extra_fields, [key]: e.target.value },
                            })
                          }
                        />
                      </div>
                    ))}
                  </fieldset>
                )}

                <div className="editor-actions">
                  <button className="primary-pill-btn" type="submit" disabled={savingEditor}>
                    {savingEditor ? "Zapisywanie..." : "Zapisz zmiany"}
                  </button>
                  {isSupervisorOrAdmin && (
                    <button
                      className="secondary-btn"
                      type="button"
                      onClick={() => {
                        setReassignError(null);
                        setReassignTargets([
                          { id: selectedCase.id, version: selectedCase.version },
                        ]);
                      }}
                    >
                      Przepisz sprawę
                    </button>
                  )}
                  <button className="secondary-btn" type="button" onClick={closeEditor}>
                    Anuluj
                  </button>
                </div>
              </form>

              <CaseEditorExtras
                caseId={selectedCase.id}
                caseVersion={selectedCase.version}
                assignableUsers={assignableUsers}
              />
            </aside>
          )}
        </div>
      </main>

      {/* Spec 015: Sticky Bulk Action Bar */}
      {selectedIds.length > 0 && (
        <div className="bulk-action-bar" role="region" aria-label="Akcje zbiorcze">
          <span>Zaznaczono: {selectedIds.length} spraw</span>
          <div className="bulk-action-buttons">
            <button
              className="secondary-btn"
              type="button"
              disabled={bulkBusy}
              onClick={() => setBulkConfirm({ kind: "set_status", status: "closed" })}
            >
              Zmień status
            </button>
            <button
              className="secondary-btn"
              type="button"
              disabled={bulkBusy}
              onClick={() => setBulkConfirm({ kind: "archive" })}
            >
              Archiwizuj
            </button>
            {isSupervisorOrAdmin && (
              <button
                className="primary-pill-btn"
                type="button"
                disabled={bulkBusy}
                onClick={() => {
                  setReassignError(null);
                  setReassignTargets(
                    cases
                      .filter((c) => selectedIds.includes(c.id))
                      .map((c) => ({ id: c.id, version: c.version }))
                  );
                }}
              >
                Przepisz zaznaczone
              </button>
            )}
            <button
              className="secondary-btn"
              type="button"
              disabled={bulkBusy}
              onClick={() => setSelectedIds([])}
            >
              Odznacz wszystkie
            </button>
          </div>
        </div>
      )}

      {bulkConfirm && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bulk-confirm-heading"
          >
            <h2 id="bulk-confirm-heading">
              {bulkConfirm.kind === "archive"
                ? "Archiwizacja zbiorcza"
                : "Zmiana statusu zaznaczonych spraw"}
            </h2>
            <p className="cases-subtitle">
              Liczba wybranych spraw: <strong>{selectedIds.length}</strong>.
            </p>
            {bulkConfirm.kind === "set_status" && (
              <div className="form-field">
                <label htmlFor="bulk-status-select">Nowy status</label>
                <select
                  id="bulk-status-select"
                  value={bulkConfirm.status}
                  onChange={(e) =>
                    setBulkConfirm({
                      kind: "set_status",
                      status: e.target.value as CaseStatus,
                    })
                  }
                >
                  <option value="closed">Zamknięta</option>
                  <option value="open">Otwarta</option>
                </select>
              </div>
            )}
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                disabled={bulkBusy}
                onClick={() => void executeBulkAction()}
              >
                {bulkBusy ? "Przetwarzanie..." : "Zatwierdź"}
              </button>
              <button
                className="secondary-btn"
                type="button"
                disabled={bulkBusy}
                onClick={() => setBulkConfirm(null)}
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}

      {reassignTargets && (
        <ReassignModal
          count={reassignTargets.length}
          assignableUsers={assignableUsers}
          busy={reassignBusy}
          error={reassignError}
          onConfirm={(targetId, reason) => void handleConfirmReassign(targetId, reason)}
          onCancel={() => setReassignTargets(null)}
        />
      )}

      {reloginContext && (
        <ReLoginModal
          expectedEmail={reloginContext.expectedEmail}
          onSuccess={handleReloginSuccess}
          onCancel={() => setReloginContext(null)}
        />
      )}

      {showCreateModal && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-case-heading"
          >
            <h2 id="create-case-heading">Nowa sprawa</h2>
            {createError && (
              <div className="error-banner" role="alert">
                {createError}
              </div>
            )}
            <form className="editor-form" onSubmit={handleCreateSubmit}>
              {isAdmin && (
                <div className="form-field">
                  <label htmlFor="create-case-number">Numer sprawy (opcjonalny)</label>
                  <input
                    id="create-case-number"
                    type="text"
                    value={createCaseNumber}
                    onChange={(e) => setCreateCaseNumber(e.target.value)}
                  />
                </div>
              )}

              <div className="form-field">
                <label htmlFor="create-title">Tytuł sprawy</label>
                <input
                  id="create-title"
                  type="text"
                  required
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                />
              </div>

              <div className="form-field">
                <label htmlFor="create-client">Klient</label>
                <input
                  id="create-client"
                  type="text"
                  required
                  value={createClientName}
                  onChange={(e) => setCreateClientName(e.target.value)}
                />
              </div>

              <div className="form-field">
                <label htmlFor="create-assigned-to">Przypisany do</label>
                <select
                  id="create-assigned-to"
                  required
                  value={createAssignedTo}
                  onChange={(e) => setCreateAssignedTo(Number(e.target.value))}
                >
                  {assignableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email}
                      {u.is_active ? "" : " (nieaktywny)"}
                    </option>
                  ))}
                </select>
              </div>

              {isAdmin && (
                <>
                  <div className="form-field">
                    <label htmlFor="create-deadline">Termin realizacji</label>
                    <input
                      id="create-deadline"
                      type="date"
                      value={createDeadline}
                      onChange={(e) => setCreateDeadline(e.target.value)}
                    />
                  </div>
                  {showPastDeadlineWarning && (
                    <div className="warning-banner" role="status">
                      Uwaga: wybrany termin już minął — sprawa zostanie od razu oznaczona jako
                      zaległa.
                    </div>
                  )}
                  <div className="form-field">
                    <label htmlFor="create-date-filed">Data wpływu</label>
                    <input
                      id="create-date-filed"
                      type="date"
                      value={createDateFiled}
                      onChange={(e) => setCreateDateFiled(e.target.value)}
                    />
                  </div>
                </>
              )}

              <div className="editor-actions">
                <button className="primary-pill-btn" type="submit" disabled={creating}>
                  {creating ? "Tworzenie..." : "Utwórz sprawę"}
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                >
                  Anuluj
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {conflict && (
        <div className="modal-backdrop">
          <div
            className="modal-card modal-conflict"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="conflict-heading"
          >
            <h2 id="conflict-heading">Konflikt edycji</h2>
            <p className="cases-subtitle">
              Inny użytkownik zapisał zmiany w tej sprawie (wersja {conflict.current.version}).
              Wybierz, co chcesz zrobić:
            </p>
            <div className="conflict-grid">
              <div className="conflict-col">
                <h3>Twoja wersja</h3>
                <p>
                  <strong>Tytuł:</strong> {conflict.pendingPayload.title ?? conflict.current.title}
                </p>
                <p>
                  <strong>Klient:</strong>{" "}
                  {conflict.pendingPayload.client_name ?? conflict.current.client_name}
                </p>
                <p>
                  <strong>Status:</strong>{" "}
                  {(conflict.pendingPayload.status ?? conflict.current.status) === "closed"
                    ? "Zamknięta"
                    : "Otwarta"}
                </p>
              </div>
              <div className="conflict-col">
                <h3>Zapisana wersja</h3>
                <p>
                  <strong>Tytuł:</strong> {conflict.current.title}
                </p>
                <p>
                  <strong>Klient:</strong> {conflict.current.client_name}
                </p>
                <p>
                  <strong>Status:</strong>{" "}
                  {conflict.current.status === "closed" ? "Zamknięta" : "Otwarta"}
                </p>
              </div>
            </div>
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => void handleConflictOverwrite()}
              >
                Nadpisz
              </button>
              <button className="secondary-btn" type="button" onClick={handleConflictDiscard}>
                Odrzuć moje zmiany
              </button>
            </div>
          </div>
        </div>
      )}
      {showPersonNotes && (
        <PersonNotesModal
          users={assignableUsers}
          onClose={() => setShowPersonNotes(false)}
        />
      )}

      {archiveConfirmCase && (
        <div className="modal-backdrop">
          <div
            className="modal-card"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="archive-confirm-heading"
          >
            <h2 id="archive-confirm-heading">Zarchiwizować otwartą sprawę?</h2>
            <p className="cases-subtitle">
              Sprawa „{archiveConfirmCase.title}” ma nadal status Otwarta. Czy na pewno chcesz ją
              przenieść do archiwum?
            </p>
            <div className="editor-actions">
              <button
                className="primary-pill-btn"
                type="button"
                onClick={() => void executeArchive(archiveConfirmCase)}
              >
                Archiwizuj sprawę
              </button>
              <button
                className="secondary-btn"
                type="button"
                onClick={() => setArchiveConfirmCase(null)}
              >
                Anuluj
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

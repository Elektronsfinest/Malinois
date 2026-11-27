import { createRootRouteWithContext, createRoute, createRouter, Outlet, redirect } from "@tanstack/react-router";
import { AdminPage } from "./components/AdminPage";
import { ArchivePage } from "./components/ArchivePage";
import { CasesPage } from "./components/CasesPage";
import { DashboardPage } from "./components/DashboardPage";
import { ImportPage } from "./components/ImportPage";
import { LoginPage } from "./components/LoginPage";
import { SettingsPage } from "./components/SettingsPage";
import type { AuthContextValue } from "./context/useAuth";

export interface RouterContext {
  auth: AuthContextValue;
}

function guardAuthenticatedAndPassword(auth: AuthContextValue) {
  if (!auth.isLoading && !auth.token) {
    throw redirect({ to: "/login" });
  }
  if (!auth.isLoading && auth.user?.must_change_password) {
    throw redirect({ to: "/settings" });
  }
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: () => <Outlet />,
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: ({ context }) => guardAuthenticatedAndPassword(context.auth),
  component: DashboardPage,
});

export interface CasesSearchParams {
  q?: string;
  status?: "open" | "closed";
  assigned_to?: number;
  deadline_from?: string;
  deadline_to?: string;
  overdue?: boolean;
  due_soon?: boolean;
  sort?: "deadline_asc" | "deadline_desc" | "updated_at_desc";
}

function parseBoolParam(val: unknown): boolean | undefined {
  if (val === true || val === "true") {
    return true;
  }
  return undefined;
}

const casesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/cases",
  validateSearch: (search: Record<string, unknown>): CasesSearchParams => {
    const out: CasesSearchParams = {};
    if (typeof search.q === "string" && search.q.trim()) {
      out.q = search.q;
    }
    if (search.status === "open" || search.status === "closed") {
      out.status = search.status;
    }
    if (search.assigned_to !== undefined && search.assigned_to !== "") {
      const n = Number(search.assigned_to);
      if (Number.isInteger(n) && n > 0) {
        out.assigned_to = n;
      }
    }
    if (typeof search.deadline_from === "string" && search.deadline_from) {
      out.deadline_from = search.deadline_from;
    }
    if (typeof search.deadline_to === "string" && search.deadline_to) {
      out.deadline_to = search.deadline_to;
    }
    if (parseBoolParam(search.overdue)) {
      out.overdue = true;
    }
    if (parseBoolParam(search.due_soon)) {
      out.due_soon = true;
    }
    if (
      search.sort === "deadline_asc" ||
      search.sort === "deadline_desc" ||
      search.sort === "updated_at_desc"
    ) {
      out.sort = search.sort;
    }
    return out;
  },
  beforeLoad: ({ context }) => guardAuthenticatedAndPassword(context.auth),
  component: CasesPage,
});

const importRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/import",
  beforeLoad: ({ context }) => guardAuthenticatedAndPassword(context.auth),
  component: ImportPage,
});

const archiveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/archive",
  beforeLoad: ({ context }) => guardAuthenticatedAndPassword(context.auth),
  component: ArchivePage,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  beforeLoad: ({ context }) => {
    if (!context.auth.isLoading && !context.auth.token) {
      throw redirect({ to: "/login" });
    }
  },
  component: SettingsPage,
});

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  beforeLoad: ({ context }) => {
    guardAuthenticatedAndPassword(context.auth);
    if (!context.auth.isLoading && context.auth.user && context.auth.user.role !== "admin") {
      throw redirect({ to: "/" });
    }
  },
  component: AdminPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: ({ context }) => {
    if (!context.auth.isLoading && context.auth.token && context.auth.user) {
      throw redirect({ to: context.auth.user.must_change_password ? "/settings" : "/" });
    }
  },
  component: LoginPage,
});

const routeTree = rootRoute.addChildren([
  dashboardRoute,
  casesRoute,
  importRoute,
  archiveRoute,
  settingsRoute,
  adminRoute,
  loginRoute,
]);

export const router = createRouter({
  routeTree,
  context: {
    auth: undefined!,
  },
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

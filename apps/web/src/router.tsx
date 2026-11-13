import { createRootRouteWithContext, createRoute, createRouter, Outlet, redirect } from "@tanstack/react-router";
import { DashboardPage } from "./components/DashboardPage";
import { LoginPage } from "./components/LoginPage";
import type { AuthContextValue } from "./context/useAuth";

export interface RouterContext {
  auth: AuthContextValue;
}

const rootRoute = createRootRouteWithContext<RouterContext>()({
  component: () => <Outlet />,
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: ({ context }) => {
    if (!context.auth.isLoading && !context.auth.token) {
      throw redirect({ to: "/login" });
    }
  },
  component: DashboardPage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  beforeLoad: ({ context }) => {
    if (!context.auth.isLoading && context.auth.token && context.auth.user) {
      throw redirect({ to: "/" });
    }
  },
  component: LoginPage,
});

const routeTree = rootRoute.addChildren([dashboardRoute, loginRoute]);

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

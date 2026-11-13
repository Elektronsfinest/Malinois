import { useEffect } from "react";
import { RouterProvider } from "@tanstack/react-router";
import { AuthProvider } from "./context/AuthContext";
import { useAuth } from "./context/useAuth";
import { router } from "./router";

function AppRouter() {
  const auth = useAuth();

  useEffect(() => {
    void router.invalidate();
  }, [auth.token, auth.user, auth.isLoading]);

  if (auth.isLoading) {
    return <p>Ładowanie...</p>;
  }

  return <RouterProvider router={router} context={{ auth }} />;
}

export function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}

export default App;

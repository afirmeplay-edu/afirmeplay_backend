import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => ({ user: { id: "demo", email: "demo@afirmeplay.local" } }),
  component: () => <Outlet />,
});

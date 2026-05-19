import { MainLayout } from '@/components/layouts/MainLayout';
import { createRootRoute, Outlet } from '@tanstack/react-router';
import { TanStackRouterDevtools } from '@tanstack/router-devtools';

export const Route = createRootRoute({
  component: () => (
    <MainLayout>
      <Outlet />
      {import.meta.env?.DEV && <TanStackRouterDevtools />}
    </MainLayout>
  ),
});

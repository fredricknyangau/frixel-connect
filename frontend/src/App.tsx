import { HelmetProvider } from 'react-helmet-async';
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { RouterProvider } from 'react-router-dom';
import { TooltipProvider } from './components/ui/tooltip';

import { queryClient } from './lib/queryClient';
import { AuthProvider } from './context/AuthContext';
import TenantStatusGuard from './components/shared/TenantStatusGuard';
import { router } from './router';

export default function App() {
  return (
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TenantStatusGuard>
            <TooltipProvider>
              <RouterProvider router={router} />
            </TooltipProvider>
          </TenantStatusGuard>
        </AuthProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </HelmetProvider>
  );
}

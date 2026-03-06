'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

// Singleton so external code (auth-context) can clear the cache on user switch.
let _queryClient: QueryClient | null = null;

export function getQueryClient(): QueryClient | null {
  return _queryClient;
}

export function QueryProvider({ children }: { readonly children: React.ReactNode }) {
  const [queryClient] = useState(() => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 60 * 1000, // 1 minute
          refetchOnWindowFocus: false,
        },
      },
    });
    _queryClient = client;
    return client;
  });

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

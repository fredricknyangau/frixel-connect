import { QueryClient } from '@tanstack/react-query';
import axios from 'axios';

/**
 * Configure TanStack Query client.
 * 
 * staleTime: 30 seconds. Data older than 30s triggers background refetch.
 * (Backend analogy: like HTTP cache-control max-age).
 * 
 * retry: 1. Retry failed requests once.
 * However, we don't want to retry 401 Unauthorized errors because 
 * they won't succeed on retry and we handle them via API interceptors.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      retry: (failureCount, error) => {
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          return false; // Do not retry on 401
        }
        return failureCount < 1; // Retry exactly once for other errors
      },
    },
    mutations: {
      onError: (error) => {
        // Default error handler: log to console in dev
        if (import.meta.env.DEV) {
          console.error('Mutation error:', error);
        }
      },
    },
  },
});

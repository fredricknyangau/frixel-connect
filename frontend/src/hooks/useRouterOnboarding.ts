/**
 * src/hooks/useRouterOnboarding.ts
 * ==================================
 * React Query hooks for the Magic Command router onboarding flow.
 *
 * The old 7-mutation hook has been replaced with 2 hooks:
 *   useInitMagic()       -POST /admin/routers/onboarding/init-magic
 *   useRouterStatus()    -GET  /admin/routers/onboarding/status/{id} (polling)
 *
 * POLLING PATTERN (same as PaymentPolling.tsx for M-Pesa STK push):
 *   The frontend polls a lightweight status endpoint every 3 seconds.
 *   When the router calls POST /setup/{token}/confirm, the backend sets
 *   status='online'. The next poll returns 'online', and the wizard advances.
 *   Polling is enabled only when we have a router_id and the status is not
 *   yet terminal ('online' or 'failed'). React Query's refetchInterval handles
 *   the polling; setting it to false stops it automatically.
 *
 * The old mutations (useInitOnboarding, useRegisterPeer, useTestTunnel,
 * useSaveCredentials, useTestAPI, useSetupProfiles, useCompleteOnboarding)
 * have been intentionally removed. The new Magic Command flow replaces all
 * of those steps with a single server-generated script that the router
 * executes autonomously.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { api } from '../lib/api';
import { queryKeys } from '../lib/queryKeys';
import { useAuthContext } from '../context/AuthContext';
import type { MagicInitResponse, RouterStatusResponse } from '../types/setup';

// ── Request types ─────────────────────────────────────────────────────────────

export interface MagicInitRequest {
  name: string;
  site_name: string;
  /**
   * Set to true when testing with MikroTik CHR on VirtualBox.
   * Changes the generated script URL from https://api.Frixel Connect.dev/...
   * to http://192.168.56.1:8000/... and removes the WireGuard commands
   * from the script (CHR and backend share the same machine).
   */
  is_chr: boolean;
}

// ── useInitMagic ──────────────────────────────────────────────────────────────

/**
 * Mutation hook for POST /admin/routers/onboarding/init-magic
 *
 * On success, the backend has:
 *   1. Created the router record (status='pending_setup')
 *   2. Generated the WireGuard keypair, API password, and setup token
 *   3. Stored everything in setup_tokens
 *   4. Pre-registered the WireGuard peer
 *
 * The response contains magic_command-the one-liner to paste into MikroTik.
 */
export function useInitMagic() {
  const queryClient = useQueryClient();
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useMutation<MagicInitResponse, AxiosError<{ detail: string }>, MagicInitRequest>({
    mutationFn: async (data) => {
      const response = await api.post<MagicInitResponse>(
        '/admin/routers/onboarding/init-magic',
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      if (tenantId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.routers.all(tenantId) });
      }
    },
  });
}

// ── useRouterStatus ───────────────────────────────────────────────────────────

/**
 * Query hook for GET /admin/routers/onboarding/status/{routerId}
 *
 * Polls every 3 seconds to detect when the router calls /confirm
 * and sets its status to 'online'.
 *
 * POLLING BEHAVIOUR (mirrors PaymentPolling.tsx pattern):
 *   - enabled=false when routerId is null/empty (before init-magic returns)
 *   - refetchInterval=3000 when enabled and status is not terminal
 *   - refetchInterval=false when status is 'online' or 'failed' (stops polling)
 *
 * The wizard component uses the returned status to decide when to advance
 * from the 'command' step to the 'complete' step.
 *
 * @param routerId  UUID string of the router to monitor
 * @param enabled   false until we have a routerId from init-magic
 */
export function useRouterStatus(routerId: string | null, enabled: boolean) {
  const { user } = useAuthContext();
  const tenantId = user?.tenant_id ?? '';

  return useQuery<RouterStatusResponse, AxiosError<{ detail: string }>>({
    queryKey: queryKeys.routers.onboarding(tenantId, routerId ?? ''),
    queryFn: async () => {
      const response = await api.get<RouterStatusResponse>(
        `/admin/routers/onboarding/status/${routerId}`,
      );
      return response.data;
    },
    enabled: enabled && !!routerId,
    // Poll every 3 seconds while waiting for the router to connect.
    // Stop polling when the status reaches a terminal state.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'online' || status === 'failed') {
        return false; // Stop polling-terminal state reached
      }
      return 3000; // Poll every 3 seconds
    },
    // Keep showing the last known status even when refetching in background.
    // Without this, the status briefly disappears between polls.
    staleTime: 0,
    // Do not retry failed status polls-a 404 means the router_id is invalid,
    // and retrying won't help. The user should restart the wizard.
    retry: false,
  });
}

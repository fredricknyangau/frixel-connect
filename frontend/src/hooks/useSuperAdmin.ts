import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { superAdminApi } from '../lib/superAdminApi';
import {
  PlatformStats,
  Tenant,
  TenantDetail,
  ImpersonationResponse,
  SuperAdminAuditEntry,
  SuperAdminProfile,
} from '../types/superAdmin';

// ─── Platform Statistics Hook ──────────────────────────────────────────────────

export const usePlatformStats = () => {
  return useQuery<PlatformStats>({
    queryKey: ['super-admin', 'stats'],
    queryFn: async () => {
      const response = await superAdminApi.get<PlatformStats>('/super-admin/stats');
      return response.data;
    },
    staleTime: 60000, // 60s as requested
  });
};

// ─── Tenants Hooks ────────────────────────────────────────────────────────────

interface GetTenantsParams {
  page: number;
  limit: number;
  status?: string;
  search?: string;
}

interface PaginatedTenantsResponse {
  tenants: Tenant[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export const useTenants = (params: GetTenantsParams) => {
  return useQuery<PaginatedTenantsResponse>({
    queryKey: ['super-admin', 'tenants', params],
    queryFn: async () => {
      const response = await superAdminApi.get<PaginatedTenantsResponse>('/super-admin/tenants', {
        params: {
          page: params.page,
          limit: params.limit,
          status_filter: params.status || undefined,
          search: params.search || undefined,
        },
      });
      return response.data;
    },
  });
};

export const useTenantDetail = (tenantId: string) => {
  return useQuery<TenantDetail>({
    queryKey: ['super-admin', 'tenants', tenantId],
    queryFn: async () => {
      const response = await superAdminApi.get<TenantDetail>(`/super-admin/tenants/${tenantId}`);
      return response.data;
    },
    enabled: !!tenantId,
  });
};

// ─── Tenant Status Mutations ──────────────────────────────────────────────────

export const useSuspendTenant = () => {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { tenantId: string; reason: string }>({
    mutationFn: async ({ tenantId, reason }) => {
      await superAdminApi.post(`/super-admin/tenants/${tenantId}/suspend`, { reason });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin', 'tenants'] });
      queryClient.invalidateQueries({ queryKey: ['super-admin', 'stats'] });
    },
  });
};

export const useReactivateTenant = () => {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (tenantId) => {
      await superAdminApi.post(`/super-admin/tenants/${tenantId}/reactivate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin', 'tenants'] });
      queryClient.invalidateQueries({ queryKey: ['super-admin', 'stats'] });
    },
  });
};

// ─── Tenant Impersonation Hook ────────────────────────────────────────────────

export const useImpersonateTenant = () => {
  return useMutation<ImpersonationResponse, Error, { tenantId: string; durationMinutes: number }>({
    mutationFn: async ({ tenantId, durationMinutes }) => {
      const response = await superAdminApi.post<ImpersonationResponse>(
        `/super-admin/tenants/${tenantId}/impersonate`,
        { duration_minutes: durationMinutes }
      );
      return response.data;
    },
  });
};

// ─── Tenant Manual Billing Hook ────────────────────────────────────────────────

export const useTriggerBilling = () => {
  return useMutation<any, Error, string>({
    mutationFn: async (tenantId) => {
      const response = await superAdminApi.post(`/super-admin/tenants/${tenantId}/billing/trigger`);
      return response.data;
    },
  });
};

// ─── Audit Log Hook ───────────────────────────────────────────────────────────

interface GetAuditLogParams {
  page: number;
  limit: number;
  action?: string;
}

interface PaginatedAuditLogResponse {
  entries: SuperAdminAuditEntry[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export const useSuperAdminAuditLog = (params: GetAuditLogParams) => {
  return useQuery<PaginatedAuditLogResponse>({
    queryKey: ['super-admin', 'audit-log', params],
    queryFn: async () => {
      const response = await superAdminApi.get<PaginatedAuditLogResponse>('/super-admin/audit-log', {
        params: {
          page: params.page,
          limit: params.limit,
          action: params.action || undefined,
        },
      });
      return response.data;
    },
  });
};

export const useCreateSuperAdmin = () => {
  const queryClient = useQueryClient();
  return useMutation<any, Error, any>({
    mutationFn: async (data) => {
      const response = await superAdminApi.post('/super-admin/accounts', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['super-admin', 'accounts'] });
    },
  });
};

export const useSuperAdmins = () => {
  return useQuery<SuperAdminProfile[]>({
    queryKey: ['super-admin', 'accounts'],
    queryFn: async () => {
      const response = await superAdminApi.get<SuperAdminProfile[]>('/super-admin/accounts');
      return response.data;
    },
  });
};

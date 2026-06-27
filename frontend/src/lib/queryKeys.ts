export const queryKeys = {
  packages: {
    all: (tenantId: string) => ['packages', 'all', tenantId] as const,
    byId: (tenantId: string, id: string) => ['packages', 'by-id', id, tenantId] as const,
  },
  payments: {
    all: (tenantId: string) => ['payments', 'all', tenantId] as const,
    admin: (tenantId: string) => ['payments', 'admin', tenantId] as const,
    reseller: (tenantId: string) => ['payments', 'reseller', tenantId] as const,
    customer: (tenantId: string) => ['payments', 'customer', tenantId] as const,
    byId: (tenantId: string, id: string) => ['payments', 'by-id', id, tenantId] as const,
    status: (tenantId: string, id: string) => ['payments', 'status', id, tenantId] as const,
    portal: (paymentId: string) => ['portal', 'payment-status', paymentId] as const,
  },
  vouchers: {
    all: (tenantId: string) => ['vouchers', 'all', tenantId] as const,
    admin: (tenantId: string) => ['vouchers', 'admin', tenantId] as const,
    reseller: (tenantId: string) => ['vouchers', 'reseller', tenantId] as const,
    customer: (tenantId: string) => ['vouchers', 'customer', tenantId] as const,
    byId: (tenantId: string, id: string) => ['vouchers', 'by-id', id, tenantId] as const,
  },
  users: {
    me: (tenantId: string) => ['users', 'me', tenantId] as const,
    adminCustomers: (tenantId: string) => ['users', 'admin-customers', tenantId] as const,
    resellerCustomers: (tenantId: string) => ['users', 'reseller-customers', tenantId] as const,
    profile: (tenantId: string) => ['users', 'profile', tenantId] as const,
  },
  routers: {
    all: (tenantId: string) => ['routers', 'all', tenantId] as const,
    byId: (tenantId: string, id: string) => ['routers', 'by-id', id, tenantId] as const,
    status: (tenantId: string, id: string) => ['routers', 'status', id, tenantId] as const,
    onboarding: (tenantId: string, routerId: string) =>
      ['routers', 'onboarding', routerId, tenantId] as const,
  },
  sessions: {
    admin: (tenantId: string) => ['sessions', 'admin', tenantId] as const,
    customer: (tenantId: string) => ['sessions', 'customer', tenantId] as const,
  },
  subscriptions: {
    mine: (tenantId: string) => ['subscriptions', 'mine', tenantId] as const,
    admin: (tenantId: string, status?: string) =>
      ['subscriptions', 'admin', tenantId, status ?? 'all'] as const,
  },
  wallets: {
    balance: (tenantId: string, resellerId: string) =>
      ['wallet', 'balance', resellerId, tenantId] as const,
    transactions: (tenantId: string, resellerId: string) =>
      ['wallet', 'transactions', resellerId, tenantId] as const,
  },
  invoices: {
    admin: (tenantId: string) => ['invoices', 'admin', tenantId] as const,
    mine: (tenantId: string) => ['invoices', 'mine', tenantId] as const,
  },
  stats: {
    dashboard: (tenantId: string) => ['stats', 'dashboard', tenantId] as const,
    systemHealth: (tenantId: string) => ['stats', 'system-health', tenantId] as const,
    stuckPayments: (tenantId: string) => ['stats', 'stuck-payments', tenantId] as const,
    auditLog: (tenantId: string, action: string, limit: number, offset: number) =>
      ['stats', 'audit-log', tenantId, action, limit, offset] as const,
  },
  tenant: {
    me: (tenantId: string) => ['tenant', 'me', tenantId] as const,
  },
} as const;

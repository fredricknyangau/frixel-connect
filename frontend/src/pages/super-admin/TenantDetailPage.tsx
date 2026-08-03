import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import axios from 'axios';
import { 
  ArrowLeft, 
  Building2, 
  CreditCard, 
  Users, 
  Activity, 
  ExternalLink,
  Loader2,
  Calendar,
  Phone,
  Mail,
  CheckCircle,
  X
} from 'lucide-react';
import { 
  useTenantDetail, 
  useSuspendTenant, 
  useReactivateTenant, 
  useImpersonateTenant 
} from '../../hooks/useSuperAdmin';
import { LoadingSpinner } from '../../components/shared/LoadingSpinner';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';

interface TenantAuditLogEntry {
  id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  metadata: Record<string, any>;
  created_at: string;
  actor?: {
    email: string;
  };
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Tabs state
  const [activeTab, setActiveTab] = useState<'overview' | 'audit'>('overview');

  // Modal states
  const [showImpersonateModal, setShowImpersonateModal] = useState(false);
  const [impersonateDuration, setImpersonateDuration] = useState<number>(30);
  const [showSuspendModal, setShowSuspendModal] = useState(false);
  const [suspendReason, setSuspendReason] = useState('');

  // Tenant Audit Logs state (fetched using impersonation token)
  const [tenantAuditLogs, setTenantAuditLogs] = useState<TenantAuditLogEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);

  // Queries
  const { data: tenant, isLoading: tenantLoading, refetch } = useTenantDetail(id || '');

  // Mutations
  const suspendMutation = useSuspendTenant();
  const reactivateMutation = useReactivateTenant();
  const impersonateMutation = useImpersonateTenant();

  // Fetch tenant-level audit logs using a temporary impersonation token
  const loadTenantAuditLogs = async () => {
    if (!id) return;
    setAuditLoading(true);
    try {
      // 1. Get a short-lived token
      const tokenRes = await impersonateMutation.mutateAsync({
        tenantId: id,
        durationMinutes: 5,
      });

      // 2. Fetch standard tenant audit logs with token
      const logsRes = await axios.get(
        `${import.meta.env.VITE_API_BASE_URL}/admin/audit-log`,
        {
          headers: {
            Authorization: `Bearer ${tokenRes.impersonation_token}`,
          },
        }
      );
      setTenantAuditLogs(logsRes.data.items || []);
    } catch (err: any) {
      toast.error('Failed to load tenant audit logs');
      console.error(err);
    } finally {
      setAuditLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'audit' && tenantAuditLogs.length === 0) {
      loadTenantAuditLogs();
    }
  }, [activeTab]);

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleDateString('en-KE', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  const formatKES = (amount: number) => {
    return new Intl.NumberFormat('en-KE', {
      style: 'currency',
      currency: 'KES',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  // Impersonate Action
  const handleStartImpersonation = () => {
    if (!id || !tenant) return;

    impersonateMutation.mutate(
      { tenantId: id, durationMinutes: impersonateDuration },
      {
        onSuccess: (data) => {
          toast.success(`Opening impersonation session for ${tenant.business_name}`);
          
          // Open new tab
          const newTab = window.open('/admin/dashboard', '_blank');
          if (newTab) {
            const handleReady = (event: MessageEvent) => {
              if (event.origin === window.location.origin && event.data === 'impersonation_ready') {
                newTab.postMessage(
                  { type: 'impersonation_token', token: data.impersonation_token },
                  window.location.origin
                );
                window.removeEventListener('message', handleReady);
              }
            };
            window.addEventListener('message', handleReady);
          }
          setShowImpersonateModal(false);
        },
        onError: (err) => {
          toast.error(err.message || 'Impersonation failed');
        }
      }
    );
  };

  // Suspend Action
  const handleConfirmSuspend = () => {
    if (!id || !tenant || suspendReason.length < 10) return;

    suspendMutation.mutate(
      { tenantId: id, reason: suspendReason },
      {
        onSuccess: () => {
          toast.success(`Suspended tenant ${tenant.business_name}`);
          setShowSuspendModal(false);
          setSuspendReason('');
          refetch();
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to suspend tenant');
        }
      }
    );
  };

  // Reactivate Action
  const handleReactivate = () => {
    if (!id || !tenant) return;

    reactivateMutation.mutate(id, {
      onSuccess: () => {
        toast.success(`Reactivated tenant ${tenant.business_name}`);
        refetch();
      },
      onError: (err) => {
        toast.error(err.message || 'Failed to reactivate tenant');
      }
    });
  };

  if (tenantLoading) {
    return <LoadingSpinner size="lg" className="text-red-500" />;
  }

  if (!tenant) {
    return (
      <div className="text-center py-12 space-y-4">
        <p className="text-slate-400">Tenant not found.</p>
        <Button onClick={() => navigate('/super-admin/tenants')} size="sm">
          Back to Tenants
        </Button>
      </div>
    );
  }

  // Safe checks
  const statsObj = tenant.stats || {
    total_customers: 0,
    active_customers: 0,
    total_active_routers: 0,
    total_active_vouchers: 0,
    total_revenue_kes: 0,
    last_payment_at: null,
  };

  return (
    <div className="space-y-6">
      <Helmet>
        <title>{`⚠ SA | ${tenant.business_name} | Frixel Connect`}</title>
      </Helmet>

      {/* Top Navigation */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/super-admin/tenants')}
            className="p-1.5 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-100">{tenant.business_name}</h1>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                tenant.status === 'active'
                  ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                  : tenant.status === 'suspended'
                  ? "bg-red-950/20 text-red-400 border-red-900/30"
                  : "bg-slate-950/40 text-slate-400 border-slate-800"
              }`}>
                {tenant.status}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 font-mono mt-0.5">Tenant ID: {tenant.id}</p>
          </div>
        </div>

        {/* Top Actions */}
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => setShowImpersonateModal(true)}
            className="bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs h-8.5 flex items-center justify-center gap-1.5"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Impersonate Tenant</span>
          </Button>

          {tenant.status !== 'suspended' ? (
            <Button
              onClick={() => setShowSuspendModal(true)}
              className="bg-red-950/25 border border-red-900/30 text-red-400 hover:bg-red-950/40 font-semibold text-xs h-8.5"
            >
              <span>Suspend Tenant</span>
            </Button>
          ) : (
            <Button
              onClick={handleReactivate}
              disabled={reactivateMutation.isPending}
              className="bg-emerald-950/25 border border-emerald-900/30 text-emerald-400 hover:bg-emerald-950/40 font-semibold text-xs h-8.5 flex items-center justify-center gap-1.5"
            >
              {reactivateMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              <span>Reactivate Tenant</span>
            </Button>
          )}
        </div>
      </div>

      {/* Stats Row (4 cards) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Revenue */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 flex items-center gap-4">
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-850 text-slate-400">
            <CreditCard className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider font-bold text-slate-500">Total Revenue</p>
            <p className="text-lg font-extrabold text-slate-100 mt-0.5">{formatKES(statsObj.total_revenue_kes)}</p>
          </div>
        </div>

        {/* Total Customers */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 flex items-center gap-4">
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-850 text-slate-400">
            <Users className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider font-bold text-slate-500">Customers</p>
            <p className="text-lg font-extrabold text-slate-100 mt-0.5">
              {statsObj.active_customers} <span className="text-xs text-slate-500">/ {statsObj.total_customers} active</span>
            </p>
          </div>
        </div>

        {/* Active Routers */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 flex items-center gap-4">
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-850 text-slate-400">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider font-bold text-slate-500">Active Routers</p>
            <p className="text-lg font-extrabold text-slate-100 mt-0.5">{statsObj.total_active_routers}</p>
          </div>
        </div>

        {/* Active Vouchers */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 flex items-center gap-4">
          <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-850 text-slate-400">
            <CheckCircle className="h-5 w-5 animate-pulse text-emerald-500" />
          </div>
          <div>
            <p className="text-[10px] uppercase font-mono tracking-wider font-bold text-slate-500">Active Vouchers</p>
            <p className="text-lg font-extrabold text-slate-100 mt-0.5">{statsObj.total_active_vouchers}</p>
          </div>
        </div>
      </div>

      {/* Tabs Menu */}
      <div className="flex gap-1 border-b border-slate-800">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors relative ${
            activeTab === 'overview' ? 'text-red-400' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Overview</span>
          {activeTab === 'overview' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-red-500" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`px-4 py-2.5 text-xs font-semibold uppercase tracking-wider transition-colors relative ${
            activeTab === 'audit' ? 'text-red-400' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Audit Log</span>
          {activeTab === 'audit' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-red-500" />
          )}
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && (
        <div className="grid gap-6 md:grid-cols-2">
          {/* Business details */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5 space-y-4">
            <h3 className="text-sm font-semibold tracking-tight text-slate-200 flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-slate-400" />
              <span>Business Profile</span>
            </h3>
            
            <div className="divide-y divide-slate-850 text-xs">
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Business Name</span>
                <span className="font-semibold text-slate-250">{tenant.business_name}</span>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500 flex items-center gap-1"><Mail className="h-3 w-3" /> Owner Email</span>
                <span className="font-semibold text-slate-250">{tenant.owner_email}</span>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500 flex items-center gap-1"><Phone className="h-3 w-3" /> Owner Phone</span>
                <span className="font-mono text-slate-250">{tenant.owner_phone}</span>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Created Date</span>
                <span className="font-semibold text-slate-250">{formatDate(tenant.created_at)}</span>
              </div>
            </div>
          </div>

          {/* Subscription & Billing */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5 space-y-4">
            <h3 className="text-sm font-semibold tracking-tight text-slate-200 flex items-center gap-1.5">
              <Calendar className="h-4 w-4 text-slate-400" />
              <span>Subscription & Billing</span>
            </h3>

            <div className="divide-y divide-slate-850 text-xs">
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Subscription Tier</span>
                <Badge className="bg-red-950/40 text-red-400 border border-red-900/30 capitalize text-[10px]">
                  {tenant.subscription_tier}
                </Badge>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Customer Capacity Limit</span>
                <span className="font-semibold text-slate-250">{tenant.max_customers} users max</span>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Next Billing Renewal</span>
                <span className="font-semibold text-slate-250">
                  {tenant.next_billing_date ? formatDate(tenant.next_billing_date) : 'N/A'}
                </span>
              </div>
              <div className="flex py-2.5 justify-between">
                <span className="text-slate-500">Last Payment Activity</span>
                <span className="font-semibold text-slate-250">
                  {statsObj.last_payment_at ? formatDate(statsObj.last_payment_at) : 'No payment activity'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/10 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight text-slate-200">Tenant Action Log</h3>
            {auditLoading && <Loader2 className="h-4 w-4 animate-spin text-red-500" />}
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-slate-950/40">
            <table className="min-w-full divide-y divide-slate-800/80 text-left text-xs text-slate-350">
              <thead className="bg-slate-950/80 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Timestamp</th>
                  <th className="px-4 py-2.5">Actor</th>
                  <th className="px-4 py-2.5">Action</th>
                  <th className="px-4 py-2.5">Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {tenantAuditLogs.length > 0 ? (
                  tenantAuditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-900/30 transition-colors">
                      <td className="px-4 py-2.5 text-slate-400">{formatDate(log.created_at)}</td>
                      <td className="px-4 py-2.5">{log.actor?.email || 'System'}</td>
                      <td className="px-4 py-2.5 font-mono text-red-400">{log.action}</td>
                      <td className="px-4 py-2.5 capitalize">{log.target_type}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                      {auditLoading ? 'Fetching tenant logs...' : 'No logs recorded for this tenant.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── MODALS & DIALOGS ────────────────────────────────────────────────── */}

      {/* Impersonate Dialog */}
      {showImpersonateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-850 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100">Impersonate Tenant</h3>
              <button 
                onClick={() => setShowImpersonateModal(false)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            
            <div className="space-y-2 text-slate-350 text-xs">
              <p>You are about to open a view-as-<span className="font-bold text-slate-200">{tenant.business_name}</span> session.</p>
              <p className="text-red-400 font-medium">All actions taken in this session will be logged against your super admin account.</p>
            </div>
            
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] font-mono uppercase tracking-wider font-bold text-slate-500">Session Duration</span>
              <div className="grid grid-cols-3 gap-2">
                {[15, 30, 60].map((d) => (
                  <button
                    key={d}
                    onClick={() => setImpersonateDuration(d)}
                    className={`py-1.5 rounded-lg text-xs font-semibold transition-colors border ${
                      impersonateDuration === d
                        ? "bg-teal-950/40 text-teal-400 border-teal-900/30"
                        : "bg-slate-950/30 text-slate-400 border-slate-850 hover:bg-slate-850"
                    }`}
                  >
                    {d} Min
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowImpersonateModal(false)}
                className="text-xs text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </Button>
              <Button
                onClick={handleStartImpersonation}
                disabled={impersonateMutation.isPending}
                className="bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs h-8 flex items-center justify-center gap-1.5"
              >
                {impersonateMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                <span>Start Session</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Suspend Dialog */}
      {showSuspendModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-red-950/30 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-red-400">Suspend Tenant</h3>
              <button 
                onClick={() => {
                  setShowSuspendModal(false);
                  setSuspendReason('');
                }}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            
            <div className="space-y-2 text-slate-350 text-xs">
              <p>Are you sure you want to suspend <span className="font-bold text-slate-200">{tenant.business_name}</span>?</p>
              <p className="text-red-400 font-medium">This will immediately lock out all users under this tenant.</p>
            </div>

            <div className="space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-wider font-bold text-slate-500">Suspension Reason</span>
              <textarea
                rows={3}
                placeholder="Reason must be at least 10 characters..."
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                className="w-full bg-slate-950/60 border border-slate-850 rounded-xl p-2.5 text-xs text-slate-100 placeholder:text-slate-650 focus:border-red-500 outline-none transition-colors"
              />
              <p className="text-[9px] text-slate-500">The reason is mandatory and recorded in the audit log.</p>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowSuspendModal(false);
                  setSuspendReason('');
                }}
                className="text-xs text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmSuspend}
                disabled={suspendMutation.isPending || suspendReason.length < 10}
                className="bg-red-600 hover:bg-red-500 text-white font-semibold text-xs h-8 flex items-center justify-center gap-1.5"
              >
                {suspendMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                <span>Confirm Suspension</span>
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

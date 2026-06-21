import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  Search, 
  MoreVertical, 
  ExternalLink, 
  Slash,
  Play,
  RotateCcw,
  Zap,
  Loader2,
  X
} from 'lucide-react';
import { 
  useTenants, 
  useSuspendTenant, 
  useReactivateTenant, 
  useImpersonateTenant, 
  useTriggerBilling 
} from '../../hooks/useSuperAdmin';
import { LoadingSpinner } from '../../components/shared/LoadingSpinner';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';

export default function TenantsPage() {
  // Query parameters state
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchVal, setSearchVal] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Dropdown menu state
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Dialog states
  const [impersonateTenant, setImpersonateTenant] = useState<{ id: string; name: string } | null>(null);
  const [impersonateDuration, setImpersonateDuration] = useState<number>(30);
  const [suspendTenant, setSuspendTenant] = useState<{ id: string; name: string } | null>(null);
  const [suspendReason, setSuspendReason] = useState('');
  const [reactivateTenant, setReactivateTenant] = useState<{ id: string; name: string } | null>(null);
  const [billingTenant, setBillingTenant] = useState<{ id: string; name: string } | null>(null);

  // API Queries & Mutations
  const { data, isLoading } = useTenants({
    page,
    limit: 10,
    status: statusFilter === 'all' ? undefined : statusFilter,
    search: debouncedSearch || undefined,
  });

  const suspendMutation = useSuspendTenant();
  const reactivateMutation = useReactivateTenant();
  const impersonateMutation = useImpersonateTenant();
  const triggerBillingMutation = useTriggerBilling();

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedSearch(searchVal);
    setPage(1);
  };

  const handleStatusTabChange = (status: string) => {
    setStatusFilter(status);
    setPage(1);
  };

  // Impersonate Flow
  const handleStartImpersonation = () => {
    if (!impersonateTenant) return;
    
    impersonateMutation.mutate(
      { tenantId: impersonateTenant.id, durationMinutes: impersonateDuration },
      {
        onSuccess: (data) => {
          toast.success(`Generated impersonation token for ${impersonateTenant.name}`);
          
          // Open new tab
          const newTab = window.open('/admin/dashboard', '_blank');
          if (newTab) {
            // Set up communication with the new tab
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
          setImpersonateTenant(null);
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to impersonate tenant');
        }
      }
    );
  };

  // Suspend Flow
  const handleConfirmSuspend = () => {
    if (!suspendTenant || suspendReason.length < 10) return;
    
    suspendMutation.mutate(
      { tenantId: suspendTenant.id, reason: suspendReason },
      {
        onSuccess: () => {
          toast.success(`Suspended tenant ${suspendTenant.name}`);
          setSuspendTenant(null);
          setSuspendReason('');
        },
        onError: (err) => {
          toast.error(err.message || 'Failed to suspend tenant');
        }
      }
    );
  };

  // Reactivate Flow
  const handleConfirmReactivate = () => {
    if (!reactivateTenant) return;
    
    reactivateMutation.mutate(reactivateTenant.id, {
      onSuccess: () => {
        toast.success(`Reactivated tenant ${reactivateTenant.name}`);
        setReactivateTenant(null);
      },
      onError: (err) => {
        toast.error(err.message || 'Failed to reactivate tenant');
      }
    });
  };

  // Billing Flow
  const handleConfirmBilling = () => {
    if (!billingTenant) return;

    triggerBillingMutation.mutate(billingTenant.id, {
      onSuccess: () => {
        toast.success(`Manual billing payment triggered for ${billingTenant.name}`);
        setBillingTenant(null);
      },
      onError: (err) => {
        toast.error(err.message || 'Failed to trigger billing push');
      }
    });
  };

  return (
    <div className="space-y-6">
      <Helmet>
        <title>⚠ SA | Tenants | ZealSync</title>
      </Helmet>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">ISP Tenants</h1>
          <p className="text-xs text-slate-400 mt-1">Manage and audit all registered ISP accounts on ZealSync.</p>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        {/* Status Tabs */}
        <div className="flex flex-wrap gap-1 bg-slate-900/60 p-1 rounded-xl border border-slate-800/80 max-w-fit">
          {['all', 'active', 'suspended', 'grace', 'cancelled'].map((tab) => (
            <button
              key={tab}
              onClick={() => handleStatusTabChange(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
                statusFilter === tab
                  ? 'bg-red-950/40 text-red-400 border border-red-900/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <form onSubmit={handleSearchSubmit} className="flex gap-2 max-w-md w-full">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <Input
              type="text"
              placeholder="Search by name or email..."
              value={searchVal}
              onChange={(e) => setSearchVal(e.target.value)}
              className="bg-slate-900/40 border-slate-800 text-slate-100 placeholder:text-slate-650 pl-9 focus:border-red-500 h-9"
            />
          </div>
          <Button type="submit" size="sm" className="bg-red-650 hover:bg-red-600 text-white font-semibold">
            Search
          </Button>
        </form>
      </div>

      {/* Tenants Table */}
      {isLoading ? (
        <LoadingSpinner size="lg" className="text-red-500" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/10">
          <table className="min-w-full divide-y divide-slate-800/80 text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 font-mono text-[10px] uppercase tracking-wider text-slate-550">
              <tr>
                <th className="px-4 py-3">Business Name</th>
                <th className="px-4 py-3">Owner Email</th>
                <th className="px-4 py-3">Tier</th>
                <th className="px-4 py-3">Customers</th>
                <th className="px-4 py-3">Billing</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 font-medium">
              {data?.tenants && data.tenants.length > 0 ? (
                data.tenants.map((t) => {
                  // Customers Progress
                  const current = t.current_customer_count || 0;
                  const max = t.max_customers || 100;
                  const percentage = Math.min(100, Math.round((current / max) * 100));
                  let progressBarColor = "bg-teal-500";
                  if (percentage >= 100) progressBarColor = "bg-red-500";
                  else if (percentage >= 80) progressBarColor = "bg-amber-500";

                  return (
                    <tr key={t.id} className="hover:bg-slate-900/20 transition-colors">
                      <td className="px-4 py-3.5 font-bold text-slate-100">{t.business_name}</td>
                      <td className="px-4 py-3.5 text-slate-400">{t.owner_email}</td>
                      <td className="px-4 py-3.5 capitalize font-mono text-slate-400">{t.subscription_tier}</td>
                      <td className="px-4 py-3.5 space-y-1">
                        <div className="flex items-center justify-between text-[10px] text-slate-400">
                          <span>{current} / {max}</span>
                          <span>{percentage}%</span>
                        </div>
                        <div className="h-1 w-24 bg-slate-850 rounded-full overflow-hidden border border-slate-800/50">
                          <div className={`h-full ${progressBarColor}`} style={{ width: `${percentage}%` }} />
                        </div>
                      </td>
                      <td className="px-4 py-3.5 capitalize">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                          t.billing_status === 'active'
                            ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                            : t.billing_status === 'grace'
                            ? "bg-amber-950/20 text-amber-400 border-amber-900/30"
                            : "bg-red-950/20 text-red-400 border-red-900/30"
                        }`}>
                          {t.billing_status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 capitalize">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                          t.status === 'active'
                            ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                            : t.status === 'suspended'
                            ? "bg-red-950/20 text-red-400 border-red-900/30"
                            : "bg-slate-950/40 text-slate-400 border-slate-800"
                        }`}>
                          {t.status}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right relative">
                        <button
                          onClick={() => setOpenMenuId(openMenuId === t.id ? null : t.id)}
                          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                        
                        {/* Action Dropdown Panel */}
                        {openMenuId === t.id && (
                          <>
                            {/* Backdrop overlay to close menu */}
                            <div className="fixed inset-0 z-40" onClick={() => setOpenMenuId(null)} />
                            
                            <div className="absolute right-4 mt-1 w-44 rounded-xl bg-slate-900 border border-slate-800 shadow-xl z-50 py-1.5 text-left text-xs font-semibold text-slate-200">
                              <Link
                                to={`/super-admin/tenants/${t.id}`}
                                className="flex items-center gap-2 px-3 py-2 hover:bg-slate-800 hover:text-white transition-colors"
                              >
                                <ExternalLink className="h-3.5 w-3.5 text-slate-450" />
                                <span>View Details</span>
                              </Link>
                              
                              <button
                                onClick={() => {
                                  setImpersonateTenant({ id: t.id, name: t.business_name });
                                  setOpenMenuId(null);
                                }}
                                className="flex items-center gap-2 w-full px-3 py-2 hover:bg-slate-800 hover:text-white text-teal-400 transition-colors"
                              >
                                <Play className="h-3.5 w-3.5" />
                                <span>Impersonate</span>
                              </button>

                              <button
                                onClick={() => {
                                  setBillingTenant({ id: t.id, name: t.business_name });
                                  setOpenMenuId(null);
                                }}
                                className="flex items-center gap-2 w-full px-3 py-2 hover:bg-slate-800 hover:text-white text-amber-400 transition-colors"
                              >
                                <Zap className="h-3.5 w-3.5" />
                                <span>Trigger Billing</span>
                              </button>

                              {t.status !== 'suspended' ? (
                                <button
                                  onClick={() => {
                                    setSuspendTenant({ id: t.id, name: t.business_name });
                                    setOpenMenuId(null);
                                  }}
                                  className="flex items-center gap-2 w-full px-3 py-2 hover:bg-slate-800 hover:text-red-400 text-red-500 transition-colors"
                                >
                                  <Slash className="h-3.5 w-3.5" />
                                  <span>Suspend</span>
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    setReactivateTenant({ id: t.id, name: t.business_name });
                                    setOpenMenuId(null);
                                  }}
                                  className="flex items-center gap-2 w-full px-3 py-2 hover:bg-slate-800 hover:text-emerald-450 text-emerald-500 transition-colors"
                                >
                                  <RotateCcw className="h-3.5 w-3.5" />
                                  <span>Reactivate</span>
                                </button>
                              )}
                            </div>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500 text-xs">
                    No ISP business tenants match these parameters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t border-slate-850">
          <p className="text-[11px] text-slate-500">
            Showing Page <span className="font-semibold text-slate-300">{page}</span> of{' '}
            <span className="font-semibold text-slate-300">{data.pages}</span> ({data.total} total)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="xs"
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="text-xs border-slate-800 hover:bg-slate-800 disabled:opacity-30"
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="xs"
              onClick={() => setPage(Math.min(data.pages, page + 1))}
              disabled={page === data.pages}
              className="text-xs border-slate-800 hover:bg-slate-800 disabled:opacity-30"
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* ─── MODALS & DIALOGS ────────────────────────────────────────────────── */}

      {/* Impersonate Dialog */}
      {impersonateTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-850 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100">Impersonate Tenant</h3>
              <button 
                onClick={() => setImpersonateTenant(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-2 text-slate-350 text-xs">
              <p>You are about to open a view-as-<span className="font-bold text-slate-200">{impersonateTenant.name}</span> session.</p>
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
                onClick={() => setImpersonateTenant(null)}
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
      {suspendTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-red-950/30 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-red-400">Suspend Tenant</h3>
              <button 
                onClick={() => {
                  setSuspendTenant(null);
                  setSuspendReason('');
                }}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            
            <div className="space-y-2 text-slate-350 text-xs">
              <p>Are you sure you want to suspend <span className="font-bold text-slate-200">{suspendTenant.name}</span>?</p>
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
                  setSuspendTenant(null);
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

      {/* Reactivate Dialog */}
      {reactivateTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-850 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100">Reactivate Tenant</h3>
              <button 
                onClick={() => setReactivateTenant(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            
            <p className="text-slate-350 text-xs">
              Are you sure you want to reactivate <span className="font-bold text-slate-200">{reactivateTenant.name}</span>? All users under this tenant will be allowed to log in again immediately.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setReactivateTenant(null)}
                className="text-xs text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmReactivate}
                disabled={reactivateMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs h-8 flex items-center justify-center gap-1.5"
              >
                {reactivateMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                <span>Confirm Reactivation</span>
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Trigger Billing Dialog */}
      {billingTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-850 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100">Trigger Platform Billing</h3>
              <button 
                onClick={() => setBillingTenant(null)}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            
            <p className="text-slate-350 text-xs">
              This will trigger a manual M-Pesa STK push for ZealSync platform fees directly to the owner's phone for <span className="font-bold text-slate-200">{billingTenant.name}</span>. Proceed?
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setBillingTenant(null)}
                className="text-xs text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmBilling}
                disabled={triggerBillingMutation.isPending}
                className="bg-red-600 hover:bg-red-500 text-white font-semibold text-xs h-8 flex items-center justify-center gap-1.5"
              >
                {triggerBillingMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                <span>Send STK Push</span>
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

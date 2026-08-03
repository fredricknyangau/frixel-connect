import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  Building2, 
  CreditCard, 
  Activity, 
  ChevronRight,
  TrendingUp,
  Clock
} from 'lucide-react';
import { 
  usePlatformStats, 
  useTenants, 
  useSuperAdminAuditLog 
} from '../../hooks/useSuperAdmin';
import { LoadingSpinner } from '../../components/shared/LoadingSpinner';
import { Badge } from '../../components/ui/badge';
import { cn } from '../../lib/utils';

export default function SuperAdminDashboardPage() {
  const { data: stats, isLoading: statsLoading } = usePlatformStats();
  const { data: tenantsData, isLoading: tenantsLoading } = useTenants({ page: 1, limit: 5 });
  const { data: auditData, isLoading: auditLoading } = useSuperAdminAuditLog({ page: 1, limit: 10 });

  const isLoading = statsLoading || tenantsLoading || auditLoading;

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleDateString('en-KE', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return isoStr;
    }
  };

  const formatTimeAgo = (isoStr: string) => {
    try {
      const diff = Date.now() - new Date(isoStr).getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return 'Just now';
      if (mins < 60) return `${mins}m ago`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `${hours}h ago`;
      const days = Math.floor(hours / 24);
      return `${days}d ago`;
    } catch {
      return 'Recently';
    }
  };

  // Helper to format KES values
  const formatKES = (amount: number) => {
    return new Intl.NumberFormat('en-KE', {
      style: 'currency',
      currency: 'KES',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (isLoading) {
    return <LoadingSpinner size="lg" className="text-red-500" />;
  }

  // Safe fallback counts
  const totalTenants = stats?.total_tenants || 0;
  const activeTenants = stats?.active_tenants || 0;
  const suspendedTenants = stats?.suspended_tenants || 0;
  const mrr = stats?.total_revenue_this_month_kes || 0;
  const todayRevenue = stats?.total_revenue_today_kes || 0;
  const activeSessions = stats?.total_active_sessions || 0;

  const starterCount = stats?.tenants_by_tier?.starter || 0;
  const growthCount = stats?.tenants_by_tier?.growth || 0;
  const scaleCount = stats?.tenants_by_tier?.scale || 0;
  const enterpriseCount = stats?.tenants_by_tier?.enterprise || 0;

  // Visual Ring for Tier Distribution
  const renderTierRing = (count: number, label: string, colorClass: string) => {
    const percentage = totalTenants > 0 ? Math.round((count / totalTenants) * 100) : 0;
    const radius = 18;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    return (
      <div className="flex items-center justify-between p-4 rounded-xl border border-slate-800 bg-slate-900/40">
        <div>
          <p className="text-xs uppercase tracking-wider font-mono text-slate-500 font-bold">{label}</p>
          <p className="text-2xl font-bold text-slate-100 mt-1">{count}</p>
          <p className="text-[10px] text-slate-400 mt-0.5">{percentage}% of system</p>
        </div>
        <div className="relative h-14 w-14 flex items-center justify-center">
          <svg className="h-full w-full -rotate-90">
            <circle
              cx="28"
              cy="28"
              r={radius}
              className="stroke-slate-850 fill-none"
              strokeWidth="3.5"
            />
            <circle
              cx="28"
              cy="28"
              r={radius}
              className={cn("fill-none transition-all duration-500 ease-in-out", colorClass)}
              strokeWidth="3.5"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
            />
          </svg>
          <span className="absolute text-[10px] font-bold text-slate-200">{percentage}%</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <Helmet>
        <title>⚠ SA | Dashboard | Frixel Connect</title>
      </Helmet>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Frixel Connect Operations</h1>
          <p className="text-xs text-slate-400 mt-1">Platform-wide statistics and system status overview.</p>
        </div>
        <Badge className="bg-red-950/40 text-red-400 border border-red-900/30 text-xs px-2.5 py-0.5">
          ⚠ SUPER ADMIN VIEW
        </Badge>
      </div>

      {/* TOP ROW: 4 Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Tenants */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-mono tracking-wider uppercase font-bold text-slate-500">Total Tenants</span>
            <Building2 className="h-4.5 w-4.5 text-slate-400" />
          </div>
          <div className="mt-2.5">
            <span className="text-3xl font-extrabold text-slate-100">{totalTenants}</span>
            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-400">
              <span className="text-emerald-400 font-semibold">{activeTenants} active</span>
              <span>•</span>
              <span className="text-red-400 font-semibold">{suspendedTenants} suspended</span>
            </div>
          </div>
        </div>

        {/* MRR */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-mono tracking-wider uppercase font-bold text-slate-500">MRR (Month)</span>
            <TrendingUp className="h-4.5 w-4.5 text-emerald-400" />
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-extrabold text-slate-100">{formatKES(mrr)}</span>
            <p className="text-[10px] text-slate-400 mt-1">Platform billing subscription fees</p>
          </div>
        </div>

        {/* Today's Revenue */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-mono tracking-wider uppercase font-bold text-slate-500">Today's Revenue</span>
            <CreditCard className="h-4.5 w-4.5 text-slate-400" />
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-extrabold text-slate-100">{formatKES(todayRevenue)}</span>
            <p className="text-[10px] text-slate-400 mt-1">Confirmed payments processed today</p>
          </div>
        </div>

        {/* Active Sessions */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-mono tracking-wider uppercase font-bold text-slate-500">Active Sessions</span>
            <Activity className="h-4.5 w-4.5 text-rose-500" />
          </div>
          <div className="mt-2.5">
            <span className="text-3xl font-extrabold text-slate-100">{activeSessions}</span>
            <p className="text-[10px] text-slate-400 mt-1">Concurrent user sessions across all hotspots</p>
          </div>
        </div>
      </div>

      {/* SECOND ROW: Tier Breakdown */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {renderTierRing(starterCount, 'Starter', 'stroke-teal-500')}
        {renderTierRing(growthCount, 'Growth', 'stroke-indigo-500')}
        {renderTierRing(scaleCount, 'Scale', 'stroke-amber-500')}
        {renderTierRing(enterpriseCount, 'Enterprise', 'stroke-rose-500')}
      </div>

      {/* THIRD ROW: Two Columns */}
      <div className="grid gap-6 lg:grid-cols-12">
        
        {/* LEFT: Recent Tenants (last 5) */}
        <div className="lg:col-span-7 rounded-xl border border-slate-800 bg-slate-900/30 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-slate-400" />
              <h2 className="text-sm font-semibold tracking-tight text-slate-200">Recent Signups</h2>
            </div>
            <Link 
              to="/super-admin/tenants"
              className="text-[11px] font-semibold text-red-400 hover:text-red-300 transition-colors flex items-center"
            >
              <span>View all tenants</span>
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="overflow-x-auto rounded-lg border border-slate-800/80 bg-slate-950/40">
            <table className="min-w-full divide-y divide-slate-800/80 text-left text-xs text-slate-350">
              <thead className="bg-slate-950/80 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Business Name</th>
                  <th className="px-4 py-2.5">Tier</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Joined</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {tenantsData?.tenants && tenantsData.tenants.length > 0 ? (
                  tenantsData.tenants.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-900/30 transition-colors">
                      <td className="px-4 py-3 font-semibold text-slate-100">{t.business_name}</td>
                      <td className="px-4 py-3 capitalize font-mono text-slate-400">{t.subscription_tier}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase border",
                          t.status === 'active' 
                            ? "bg-emerald-950/30 text-emerald-400 border-emerald-900/30"
                            : t.status === 'suspended'
                            ? "bg-red-950/30 text-red-400 border-red-900/30"
                            : "bg-slate-950/40 text-slate-400 border-slate-800"
                        )}>
                          {t.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{formatDate(t.created_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                      No tenants signed up yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT: Recent Audit Log (last 10) */}
        <div className="lg:col-span-5 rounded-xl border border-slate-800 bg-slate-900/30 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-slate-400" />
              <h2 className="text-sm font-semibold tracking-tight text-slate-200">System Activity</h2>
            </div>
            <Link 
              to="/super-admin/audit-log"
              className="text-[11px] font-semibold text-red-400 hover:text-red-300 transition-colors flex items-center"
            >
              <span>View full log</span>
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>

          <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
            {auditData?.entries && auditData.entries.length > 0 ? (
              auditData.entries.map((entry) => (
                <div 
                  key={entry.id}
                  className="flex items-start justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-850 hover:bg-slate-900/20 transition-colors"
                >
                  <div className="space-y-1">
                    <span className="inline-block font-mono text-[9px] uppercase font-bold text-red-400 bg-red-950/20 px-1.5 py-0.5 rounded border border-red-900/30">
                      {entry.action}
                    </span>
                    <p className="text-[11px] text-slate-350">
                      Target: <span className="font-mono text-slate-400">{entry.target_type || 'system'}</span>
                      {entry.ip_address && <span className="text-[9px] text-slate-500 ml-1.5 font-mono">({entry.ip_address})</span>}
                    </p>
                  </div>
                  <span className="text-[10px] text-slate-500 whitespace-nowrap mt-0.5">
                    {formatTimeAgo(entry.created_at)}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-center py-12 text-slate-500 text-xs">
                No system activity recorded yet.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}


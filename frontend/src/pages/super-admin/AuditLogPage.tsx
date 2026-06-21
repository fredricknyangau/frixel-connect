import { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { 
  ChevronDown, 
  ChevronUp, 
  Filter,
  Clock
} from 'lucide-react';
import { useSuperAdminAuditLog } from '../../hooks/useSuperAdmin';
import { LoadingSpinner } from '../../components/shared/LoadingSpinner';
import { Button } from '../../components/ui/button';

const COMMON_ACTIONS = [
  { value: '', label: 'All Actions' },
  { value: 'auth.password_ok', label: 'Password Check OK' },
  { value: 'auth.login_success', label: 'Login Success' },
  { value: 'tenant.list', label: 'List Tenants' },
  { value: 'tenant.view', label: 'View Tenant Details' },
  { value: 'tenant.suspend', label: 'Suspend Tenant' },
  { value: 'tenant.reactivate', label: 'Reactivate Tenant' },
  { value: 'impersonation.start', label: 'Start Impersonation' },
  { value: 'super_admin.create', label: 'Create SA Account' },
];

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useSuperAdminAuditLog({
    page,
    limit: 25,
    action: actionFilter || undefined,
  });

  const formatDate = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleDateString('en-KE', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  const handleActionFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setActionFilter(e.target.value);
    setPage(1);
    setExpandedId(null);
  };

  const toggleRow = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-6">
      <Helmet>
        <title>⚠ SA | Audit Log | ZealSync</title>
      </Helmet>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Super Admin Audit Logs</h1>
          <p className="text-xs text-slate-400 mt-1">Immutable chronological record of all administrative actions.</p>
        </div>
      </div>

      {/* Action Filter */}
      <div className="flex items-center gap-3 bg-slate-900/40 p-4 rounded-xl border border-slate-800 max-w-fit">
        <Filter className="h-4 w-4 text-slate-500" />
        <span className="text-xs font-semibold text-slate-400">Filter Action:</span>
        <select
          value={actionFilter}
          onChange={handleActionFilterChange}
          className="bg-slate-950 border border-slate-850 rounded-lg text-xs font-semibold text-slate-200 py-1 px-3 outline-none focus:border-red-500 cursor-pointer"
        >
          {COMMON_ACTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Audit Log Table */}
      {isLoading ? (
        <LoadingSpinner size="lg" className="text-red-500" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/10">
          <table className="min-w-full divide-y divide-slate-800/80 text-left text-xs text-slate-300">
            <thead className="bg-slate-950/60 font-mono text-[10px] uppercase tracking-wider text-slate-550">
              <tr>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Operator (Email)</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 font-medium">
              {data?.entries && data.entries.length > 0 ? (
                data.entries.map((entry) => {
                  const isExpanded = expandedId === entry.id;
                  
                  return (
                    <>
                      <tr 
                        key={entry.id} 
                        onClick={() => toggleRow(entry.id)}
                        className={`cursor-pointer hover:bg-slate-900/20 transition-colors ${
                          isExpanded ? 'bg-slate-900/10' : ''
                        }`}
                      >
                        <td className="px-4 py-3.5 text-slate-400 font-mono flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5 text-slate-600" />
                          <span>{formatDate(entry.created_at)}</span>
                        </td>
                        <td className="px-4 py-3.5 font-semibold text-slate-100">{entry.super_admin_email}</td>
                        <td className="px-4 py-3.5">
                          <span className="inline-block font-mono text-[9px] uppercase font-bold text-red-400 bg-red-950/20 px-2 py-0.5 rounded border border-red-900/30">
                            {entry.action}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="text-slate-400 capitalize">{entry.target_type || 'system'}</span>
                          {entry.target_id && (
                            <span className="text-[10px] text-slate-600 font-mono block mt-0.5">ID: {entry.target_id}</span>
                          )}
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <button className="p-1 rounded text-slate-500 hover:text-slate-200 transition-colors">
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </button>
                        </td>
                      </tr>
                      
                      {/* Expanded Metadata row */}
                      {isExpanded && (
                        <tr>
                          <td colSpan={5} className="bg-slate-950/80 px-6 py-4 border-t border-b border-slate-800">
                            <div className="space-y-2">
                              <p className="text-[10px] font-mono uppercase tracking-wider font-bold text-slate-500">
                                Event Payload (Metadata JSON)
                              </p>
                              <pre className="rounded-xl border border-slate-850 bg-slate-950 p-4 font-mono text-[11px] text-teal-400 leading-relaxed overflow-x-auto">
                                {JSON.stringify(entry.metadata, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-slate-500 text-xs">
                    No system audit logs found.
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
            <span className="font-semibold text-slate-300">{data.pages}</span> ({data.total} total logs)
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
    </div>
  );
}

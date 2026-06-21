export default function SuperAdminDashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
          Platform Overview
        </h1>
      </div>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-sm">
          <div className="text-sm font-medium text-slate-400">Total Tenants</div>
          <div className="mt-2 text-3xl font-semibold text-slate-100">0</div>
        </div>
      </div>
    </div>
  );
}

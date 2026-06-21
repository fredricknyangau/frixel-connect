import { useParams } from 'react-router-dom';

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
          Tenant Details
        </h1>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <p className="text-slate-400">Viewing tenant ID: <span className="font-mono text-teal-400">{id}</span></p>
      </div>
    </div>
  );
}

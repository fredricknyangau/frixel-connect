export default function SuperAdminLoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <div className="w-full max-w-md space-y-8 rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
            ZealSync Super Admin
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Secure administrative gateway. TOTP authentication required.
          </p>
        </div>
        <div className="mt-8 space-y-6">
          <div className="rounded-md bg-slate-950 p-4 border border-slate-800 text-sm text-slate-400">
            Stub Login Page. Use database intervention if credentials are lost.
          </div>
        </div>
      </div>
    </div>
  );
}

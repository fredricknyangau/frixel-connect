import { useAuthContext } from '../../context/AuthContext';
import { Button } from '../ui/button';

export default function TenantSuspendedPage() {
  const { user, logout } = useAuthContext();
  const isAdmin = user?.role === 'admin';

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-4 text-center">
      <div className="max-w-md space-y-6">
        <div className="mx-auto w-16 h-16 bg-destructive/10 rounded-full flex items-center justify-center">
          <span className="text-3xl text-destructive">⚠️</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">Access Suspended</h1>
        <p className="text-muted-foreground">
          {isAdmin
            ? "Your ISP's ZealSync subscription has lapsed or been suspended. Please pay the outstanding balance to restore services immediately."
            : "This service provider's account is temporarily unavailable. Please contact your ISP support team for further details."}
        </p>
        <div className="flex flex-col gap-2">
          {isAdmin && (
            <Button className="w-full">
              Reactivate Account
            </Button>
          )}
          <Button variant="outline" className="w-full" onClick={logout}>
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  );
}

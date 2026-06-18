import { useState } from 'react';
import { useAuthContext } from '../../context/AuthContext';
import { useTenantPayNow } from '../../hooks/useTenant';
import { StkPendingState } from './StkPendingState';
import { Button } from '../ui/button';
import { toast } from 'sonner';

export default function TenantSuspendedPage() {
  const { user, logout } = useAuthContext();
  const isAdmin = user?.role === 'admin';
  const payNowMutation = useTenantPayNow();
  const [isPaying, setIsPaying] = useState(false);

  const handlePayNow = async () => {
    try {
      await payNowMutation.mutateAsync();
      setIsPaying(true);
      setTimeout(() => {
        setIsPaying(false);
        toast.success('Payment received successfully. Thank you!');
        window.location.reload();
      }, 15000); // 15 seconds simulation
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to initiate payment.');
    }
  };

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
        {isAdmin && isPaying ? (
          <div className="py-4 border rounded-xl bg-muted/20">
            <StkPendingState 
              title="Confirm Payment on your Phone" 
              description="An M-Pesa prompt has been sent to your registered phone number. Enter your PIN to reactivate your account." 
            />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {isAdmin && (
              <Button 
                className="w-full bg-destructive hover:bg-destructive/90"
                onClick={handlePayNow}
                disabled={payNowMutation.isPending}
              >
                {payNowMutation.isPending ? 'Initiating...' : 'Pay Now to Reactivate'}
              </Button>
            )}
            <Button variant="outline" className="w-full" onClick={logout}>
              Sign Out
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

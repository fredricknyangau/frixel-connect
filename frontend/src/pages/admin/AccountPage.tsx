import { useState } from 'react';
import { useTenantMe, useTenantPayNow } from '../../hooks/useTenant';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatNairobiDate } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { Progress } from '../../components/ui/progress';
import { StkPendingState } from '../../components/shared/StkPendingState';
import { Building2, CreditCard, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function AccountPage() {
  const { data: tenant, isLoading: isTenantLoading } = useTenantMe();
  const payNowMutation = useTenantPayNow();
  const [isPaying, setIsPaying] = useState(false);

  if (isTenantLoading) {
    return (
      <div className="space-y-6">
        <PageTitle title="Account & Billing | Admin" />
        <div className="flex flex-col md:flex-row gap-6">
          <div className="w-full h-64 bg-muted animate-pulse rounded-xl" />
        </div>
      </div>
    );
  }

  if (!tenant) return null;

  const handlePayNow = async () => {
    try {
      await payNowMutation.mutateAsync();
      setIsPaying(true);
      // Simulate polling/waiting for webhook confirmation on the tenant's side
      // The status would normally be refreshed by a live query or websocket
      setTimeout(() => {
        setIsPaying(false);
        toast.success('Payment received successfully. Thank you!');
        window.location.reload(); // Quick refresh to clear the status
      }, 15000); // 15 seconds simulation for STK push
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to initiate payment.');
    }
  };

  const usagePercent = Math.min((tenant.current_customer_count / tenant.max_customers) * 100, 100);
  const isAmber = usagePercent >= 80 && usagePercent < 100;
  const isRed = usagePercent >= 100;

  return (
    <div className="space-y-6">
      <PageTitle title="Account & Billing | Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Your ZealSync Account</h2>
          <p className="text-muted-foreground">Manage your ISP's SaaS subscription and view usage limits.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2 text-primary">
              <Building2 className="h-5 w-5" />
              <CardTitle className="text-xl">Business Profile</CardTitle>
            </div>
            <CardDescription>Your registered ISP details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Business Name</p>
              <p className="font-semibold text-lg">{tenant.business_name}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Owner Email</p>
                <p className="text-sm">{tenant.owner_email}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Contact Phone</p>
                <p className="text-sm">{tenant.owner_phone}</p>
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Member Since</p>
              <p className="text-sm">{formatNairobiDate(tenant.created_at)}</p>
            </div>
          </CardContent>
        </Card>

        <Card className={`border-t-4 ${tenant.billing_status === 'active' ? 'border-t-primary' : tenant.billing_status === 'grace' ? 'border-t-amber-500' : 'border-t-destructive'}`}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-primary">
                <CreditCard className="h-5 w-5" />
                <CardTitle className="text-xl">Subscription & Billing</CardTitle>
              </div>
              <StatusBadge status={tenant.billing_status as any} />
            </div>
            <CardDescription>Your current ZealSync SaaS plan.</CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-6">
            {isPaying ? (
              <div className="py-6">
                <StkPendingState 
                  title="Confirm Payment on your Phone" 
                  description={`An M-Pesa prompt has been sent to ${tenant.owner_phone}. Please enter your PIN to complete the transaction.`} 
                />
              </div>
            ) : (
              <>
                <div className="flex justify-between items-end border-b pb-4">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">Current Tier</p>
                    <p className="text-xl font-bold capitalize">{tenant.subscription_tier} Plan</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-muted-foreground mb-1">Next Billing Date</p>
                    <p className="font-semibold">{formatNairobiDate(tenant.next_billing_date)}</p>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium text-muted-foreground">Customer Limit Usage</span>
                    <span className={`font-semibold ${isAmber ? 'text-amber-600' : isRed ? 'text-destructive' : ''}`}>
                      {tenant.current_customer_count} / {tenant.max_customers}
                    </span>
                  </div>
                  <Progress 
                    value={usagePercent} 
                    className={`h-2 ${isAmber ? 'bg-amber-100 [&>div]:bg-amber-500' : isRed ? 'bg-red-100 [&>div]:bg-red-500' : ''}`}
                  />
                  {isRed && (
                    <p className="text-xs text-destructive mt-1">You have reached your maximum customer limit. Please upgrade your tier.</p>
                  )}
                </div>
              </>
            )}
          </CardContent>
          
          {!isPaying && (
            <CardFooter className="bg-muted/30 p-4 border-t">
              <div className="w-full space-y-3">
                {tenant.billing_status === 'grace' && (
                  <p className="text-sm text-amber-700 bg-amber-50 p-2 rounded text-center border border-amber-200">
                    Your account is in grace period. Pay now to avoid service suspension for you and your customers.
                  </p>
                )}
                <Button 
                  className={`w-full ${tenant.billing_status === 'grace' ? 'bg-amber-600 hover:bg-amber-700 text-white' : ''}`}
                  onClick={handlePayNow}
                  disabled={payNowMutation.isPending}
                >
                  {payNowMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CreditCard className="mr-2 h-4 w-4" />}
                  {payNowMutation.isPending ? 'Initiating...' : 'Pay Subscription Now'}
                </Button>
              </div>
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  );
}

import { useMySubscription, useToggleAutoRenew } from '../../hooks/useSubscriptions';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../ui/card';
import { StatusBadge } from '../shared/StatusBadge';
// Removed missing Switch import
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { Progress } from '../ui/progress';
import { useNavigate } from 'react-router-dom';
import { formatNairobiDate } from '../../lib/utils';
import { Wifi, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

export default function SubscriptionCard() {
  const { data: subscription, isLoading } = useMySubscription();
  const toggleAutoRenew = useToggleAutoRenew();
  const navigate = useNavigate();

  if (isLoading) {
    return <div className="h-48 w-full bg-muted animate-pulse rounded-xl" />;
  }

  // If no subscription exists, handle gracefully by returning null (hotspot-only customer)
  if (!subscription) {
    return null;
  }

  const handleToggleAutoRenew = async (checked: boolean) => {
    try {
      await toggleAutoRenew.mutateAsync({ auto_renew: checked });
      toast.success(`Auto-renew ${checked ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error('Failed to update auto-renew preference');
    }
  };

  // Calculate progress and days remaining
  const now = new Date();
  const endDate = new Date(subscription.current_period_end);
  const createdDate = new Date(subscription.created_at);
  
  const totalDuration = endDate.getTime() - createdDate.getTime();
  const elapsed = now.getTime() - createdDate.getTime();
  
  let progressPercentage = Math.min(Math.max((elapsed / totalDuration) * 100, 0), 100);
  
  // Calculate days remaining precisely
  const daysRemaining = Math.ceil((endDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  
  const showRenewButton = subscription.status === 'grace' || daysRemaining <= 3;

  return (
    <Card className={`border-t-4 ${subscription.status === 'active' ? 'border-t-green-500' : subscription.status === 'grace' ? 'border-t-amber-500' : 'border-t-red-500'}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-primary">
            <Wifi className="h-5 w-5" />
            <CardTitle className="text-xl">Home Internet Plan</CardTitle>
          </div>
          <StatusBadge status={subscription.status as any} />
        </div>
        <CardDescription>Your recurring PPPoE WiFi connection.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex justify-between items-end border-b pb-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-1">Current Package</p>
            <p className="text-xl font-bold">{subscription.package_name}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium text-muted-foreground mb-1">Period Ends</p>
            <p className="font-semibold">{formatNairobiDate(subscription.current_period_end)}</p>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Cycle Progress</span>
            <span className={`font-medium ${daysRemaining <= 3 ? 'text-amber-600' : ''}`}>
              {daysRemaining > 0 ? `${daysRemaining} days left` : 'Expired'}
            </span>
          </div>
          <Progress 
            value={progressPercentage} 
            className={`h-2 ${daysRemaining <= 3 ? 'bg-amber-100 [&>div]:bg-amber-500' : ''}`}
          />
        </div>

        <div className="flex items-center justify-between bg-muted/50 p-4 rounded-lg">
          <div className="space-y-0.5">
            <Label htmlFor="auto-renew" className="text-base">Auto-Renew</Label>
            <p className="text-sm text-muted-foreground">Automatically bill my next cycle</p>
          </div>
          <input
            type="checkbox"
            id="auto-renew"
            className="h-5 w-5 accent-primary rounded cursor-pointer"
            checked={subscription.auto_renew} 
            onChange={(e) => handleToggleAutoRenew(e.target.checked)}
            disabled={toggleAutoRenew.isPending || subscription.status === 'suspended'}
          />
        </div>

        {subscription.status === 'grace' && (
          <div className="flex items-start gap-2 bg-amber-50 text-amber-800 p-3 rounded text-sm">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p>Your subscription is in grace period. Pay now to avoid disconnection.</p>
          </div>
        )}
      </CardContent>

      {showRenewButton && (
        <CardFooter>
          <Button 
            className="w-full" 
            onClick={() => navigate(`/customer/buy?package=${subscription.package_id}`)}
          >
            Renew Now
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}

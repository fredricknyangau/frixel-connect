import { useSystemHealth, useStuckPayments, useRetryProvisioning } from '../../hooks/useSystemHealth';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatKES } from '../../lib/utils';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Loader2, Server, Activity, Database, AlertCircle, RefreshCw } from 'lucide-react';
import { RouterStatusBadge } from '../../components/shared/RouterStatusBadge';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';

export default function SystemHealthPage() {
  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useSystemHealth();
  const { data: stuckPayments, isLoading: stuckLoading } = useStuckPayments();
  const retryMutation = useRetryProvisioning();

  const handleRetry = async (paymentId: string) => {
    try {
      await retryMutation.mutateAsync(paymentId);
      toast.success('Provisioning retry initiated successfully.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to retry provisioning.');
    }
  };

  const handleRefresh = () => {
    refetchHealth();
    toast.success('System health data refreshed');
  };

  return (
    <div className="space-y-6">
      <PageTitle title="System Health | Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">System Health & Ops</h2>
          <p className="text-muted-foreground">Monitor platform performance, queues, and router connectivity.</p>
        </div>
        <Button variant="outline" onClick={handleRefresh} disabled={healthLoading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${healthLoading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {healthLoading && !health ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map(i => <div key={i} className="h-32 bg-muted animate-pulse rounded-xl" />)}
        </div>
      ) : health ? (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Job Queue Depth</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{health.queue_depth}</div>
              <p className="text-xs text-muted-foreground mt-1">Background tasks pending</p>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Reconciliation Backlog</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${health.reconciliation_backlog > 0 ? 'text-amber-600' : 'text-green-600'}`}>
                {health.reconciliation_backlog}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Pending C2B verifications</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Webhook Success Rate (24h)</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className={`text-3xl font-bold ${health.webhook_success_rate_24h < 95 ? 'text-destructive' : 'text-green-600'}`}>
                {health.webhook_success_rate_24h}%
              </div>
              <p className="text-xs text-muted-foreground mt-1">Successful Safaricom callbacks</p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Router Status Grid</CardTitle>
            <CardDescription>Live heartbeat monitoring for all registered MikroTik devices.</CardDescription>
          </CardHeader>
          <CardContent>
            {healthLoading && !health ? (
              <div className="flex justify-center py-8"><Loader2 className="animate-spin text-muted-foreground" /></div>
            ) : !health?.routers || health.routers.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground text-sm border border-dashed rounded-md">
                No routers configured. Add one in the Routers tab.
              </div>
            ) : (
              <div className="space-y-4">
                {health.routers.map(router => (
                  <div key={router.id} className="flex items-center justify-between p-3 rounded-lg border">
                    <div className="flex items-center gap-3">
                      <div className={`h-2 w-2 rounded-full ${router.status === 'online' ? 'bg-green-500' : router.status === 'offline' ? 'bg-red-500' : 'bg-gray-400'}`} />
                      <div>
                        <div className="font-medium text-sm">{router.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {router.last_heartbeat_at ? `Last seen ${formatDistanceToNow(new Date(router.last_heartbeat_at))} ago` : 'Never seen'}
                        </div>
                      </div>
                    </div>
                    <RouterStatusBadge status={router.status} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-amber-500" />
                  Stuck Payments
                </CardTitle>
                <CardDescription>Payments that succeeded but failed to provision a voucher.</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Payment</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Age</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stuckLoading ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-8">
                        <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ) : !stuckPayments || stuckPayments.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center py-6 text-muted-foreground text-sm">
                        No stuck payments. System is healthy.
                      </TableCell>
                    </TableRow>
                  ) : (
                    stuckPayments.map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell className="font-mono text-xs font-semibold">
                          {payment.mpesa_receipt_number || `${payment.id.substring(0, 8)}...`}
                        </TableCell>
                        <TableCell className="font-medium text-primary">{formatKES(payment.amount_kes)}</TableCell>
                        <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                          {formatDistanceToNow(new Date(payment.created_at))}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => handleRetry(payment.id)}
                            disabled={retryMutation.isPending}
                          >
                            <RefreshCw className={`mr-2 h-3 w-3 ${retryMutation.isPending ? 'animate-spin' : ''}`} />
                            Retry
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

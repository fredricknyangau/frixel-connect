import { useState } from 'react';
import { useAdminSubscriptions, useSuspendSubscription, useReactivateSubscription } from '../../hooks/useSubscriptions';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatNairobiDate } from '../../lib/utils';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Loader2, PauseCircle, PlayCircle, Search } from 'lucide-react';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';

export default function SubscriptionsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [suspendDialogId, setSuspendDialogId] = useState<string | null>(null);

  const { data: subscriptions, isLoading } = useAdminSubscriptions(statusFilter);
  const suspendMutation = useSuspendSubscription();
  const reactivateMutation = useReactivateSubscription();

  const handleSuspend = async () => {
    if (!suspendDialogId) return;
    try {
      await suspendMutation.mutateAsync(suspendDialogId);
      toast.success('Subscription suspended successfully.');
      setSuspendDialogId(null);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to suspend subscription.');
    }
  };

  const handleReactivate = async (id: string) => {
    try {
      await reactivateMutation.mutateAsync(id);
      toast.success('Subscription reactivated.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to reactivate subscription.');
    }
  };

  const tabs = ['All', 'Active', 'Grace', 'Suspended', 'Cancelled'];

  const filteredSubscriptions = subscriptions?.filter((sub) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    // In a real app we'd have customer info (name/phone) included in the subscription object, 
    // for now we filter by package_name or customer_id
    return sub.package_name.toLowerCase().includes(q) || sub.customer_id.toLowerCase().includes(q);
  }) || [];

  return (
    <div className="space-y-6">
      <PageTitle title="Subscriptions | Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Recurring Subscriptions</h2>
          <p className="text-muted-foreground">Manage active PPPoE connections and customer renewals.</p>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Subscriber Connections</CardTitle>
          <CardDescription>View and manage all recurring subscriptions.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row gap-4 justify-between mb-4">
            <div className="flex bg-muted/50 p-1 rounded-md overflow-x-auto">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setStatusFilter(tab)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-sm whitespace-nowrap transition-colors ${
                    statusFilter === tab 
                      ? 'bg-background shadow-sm text-foreground' 
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="relative w-full md:w-64">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search package or customer..."
                className="pl-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>

          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer ID</TableHead>
                  <TableHead>Package</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Period End</TableHead>
                  <TableHead>Auto-Renew</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8">
                      <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ) : filteredSubscriptions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No subscriptions found matching the criteria.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredSubscriptions.map((sub) => (
                    <TableRow key={sub.id}>
                      <TableCell className="font-mono text-xs">{sub.customer_id.substring(0, 8)}...</TableCell>
                      <TableCell className="font-medium">{sub.package_name}</TableCell>
                      <TableCell>
                        <StatusBadge status={sub.status as any} />
                      </TableCell>
                      <TableCell className="text-muted-foreground whitespace-nowrap">
                        {formatNairobiDate(sub.current_period_end)}
                      </TableCell>
                      <TableCell>
                        {sub.auto_renew ? (
                          <span className="text-green-600 font-medium text-sm bg-green-50 px-2 py-0.5 rounded">Enabled</span>
                        ) : (
                          <span className="text-muted-foreground text-sm bg-muted px-2 py-0.5 rounded">Disabled</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {sub.status === 'active' || sub.status === 'grace' ? (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                            onClick={() => setSuspendDialogId(sub.id)}
                          >
                            <PauseCircle className="h-4 w-4 mr-1" /> Suspend
                          </Button>
                        ) : sub.status === 'suspended' ? (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={() => handleReactivate(sub.id)}
                            disabled={reactivateMutation.isPending}
                          >
                            <PlayCircle className="h-4 w-4 mr-1" /> Reactivate
                          </Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={!!suspendDialogId} onOpenChange={(open) => !open && setSuspendDialogId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Suspend Subscription?</DialogTitle>
            <DialogDescription>
              This will immediately disconnect the user's PPPoE session and set their billing status to suspended. They will need to pay their outstanding balance to reactivate.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button variant="outline" onClick={() => setSuspendDialogId(null)} disabled={suspendMutation.isPending}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleSuspend} disabled={suspendMutation.isPending}>
              {suspendMutation.isPending ? 'Suspending...' : 'Yes, Suspend Connection'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

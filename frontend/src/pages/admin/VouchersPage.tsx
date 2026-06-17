import { useState, useMemo } from 'react';
import { Loader2, Copy, Ban } from 'lucide-react';
import { toast } from 'sonner';

import { useAdminVouchers, useRevokeVoucher } from '../../hooks/useVouchers';
import { useAdminCustomers } from '../../hooks/useUsers';
import { usePackages } from '../../hooks/usePackages';
import { VoucherStatus } from '../../types/vouchers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatNairobiDate } from '../../lib/utils';
import { cn } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';

export default function VouchersPage() {
  const { data: vouchers, isLoading } = useAdminVouchers();
  const { data: customers } = useAdminCustomers();
  const { data: packages } = usePackages();
  const revokeVoucher = useRevokeVoucher();

  const [statusFilter, setStatusFilter] = useState<VoucherStatus | 'all'>('all');

  const filteredVouchers = useMemo(() => {
    if (!vouchers) return [];
    let filtered = [...vouchers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (statusFilter !== 'all') {
      filtered = filtered.filter(v => v.status === statusFilter);
    }

    return filtered;
  }, [vouchers, statusFilter]);

  const getPackageName = (packageId: string) => packages?.find(p => p.id === packageId)?.name || 'Unknown';
  const getCustomerPhone = (customerId: string) => customers?.find(c => c.id === customerId)?.phone || 'Unknown';

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success('Voucher code copied to clipboard');
  };

  const handleRevoke = async (voucherId: string) => {
    try {
      await revokeVoucher.mutateAsync(voucherId);
      toast.success('Voucher revoked successfully');
    } catch (error) {
      toast.error('Failed to revoke voucher');
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Vouchers | ZealSync Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Vouchers</h2>
          <p className="text-muted-foreground">Manage active, used, and expired WiFi vouchers.</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Tabs defaultValue="all" className="w-full md:w-auto" onValueChange={(val) => setStatusFilter(val as any)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="used">Used</TabsTrigger>
            <TabsTrigger value="expired">Expired</TabsTrigger>
            <TabsTrigger value="revoked">Revoked</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Package</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead>Status</TableHead>
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
            ) : filteredVouchers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No vouchers found matching the selected filter.
                </TableCell>
              </TableRow>
            ) : (
              filteredVouchers.map((voucher) => (
                <TableRow key={voucher.id} className={cn(voucher.status !== 'active' && 'opacity-70')}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium">{voucher.code}</span>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-6 w-6" 
                        onClick={() => handleCopy(voucher.code)}
                        title="Copy code"
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                  <TableCell>{getCustomerPhone(voucher.customer_id)}</TableCell>
                  <TableCell>{getPackageName(voucher.package_id)}</TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatNairobiDate(voucher.expires_at)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={voucher.status} />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="text-destructive hover:text-destructive/90 hover:bg-destructive/10"
                        onClick={() => handleRevoke(voucher.id)}
                        disabled={voucher.status !== 'active' || revokeVoucher.isPending}
                      >
                        <Ban className="h-4 w-4 mr-2" />
                        Revoke
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
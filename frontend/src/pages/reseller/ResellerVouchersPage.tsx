import { useState, useMemo } from 'react';
import { Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';

import { useResellerVouchers } from '../../hooks/useVouchers';
import { useResellerCustomers } from '../../hooks/useUsers';
import { VoucherStatus } from '../../types/vouchers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatNairobiDate } from '../../lib/utils';
import { cn } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';

export default function ResellerVouchersPage() {
  const { data: vouchers, isLoading } = useResellerVouchers();
  const { data: customers } = useResellerCustomers();
  

  const [statusFilter, setStatusFilter] = useState<VoucherStatus | 'all'>('all');

  const filteredVouchers = useMemo(() => {
    if (!vouchers) return [];
    let filtered = [...vouchers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (statusFilter !== 'all') {
      filtered = filtered.filter(v => v.status === statusFilter);
    }

    return filtered;
  }, [vouchers, statusFilter]);

  const getCustomerPhone = (customerId: string) => customers?.find(c => c.id === customerId)?.phone || 'Unknown';

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success('Voucher code copied to clipboard');
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Vouchers | Frixel Connect Reseller" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Customer Vouchers</h2>
          <p className="text-muted-foreground">View vouchers generated for your customers.</p>
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
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredVouchers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
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
                  <TableCell>{voucher.package_name || 'Unknown'}</TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatNairobiDate(voucher.expires_at)}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={voucher.status} />
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

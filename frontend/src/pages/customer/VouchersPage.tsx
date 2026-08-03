import { useState, useMemo } from 'react';
import { Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';

import { useCustomerVouchers } from '../../hooks/useVouchers';
import { VoucherStatus } from '../../types/vouchers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatNairobiDate } from '../../lib/utils';
import { cn } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';

export default function CustomerVouchersPage() {
  const { data: vouchers, isLoading } = useCustomerVouchers();
  

  const [statusFilter, setStatusFilter] = useState<VoucherStatus | 'all'>('all');

  const filteredVouchers = useMemo(() => {
    if (!vouchers) return [];
    let filtered = [...vouchers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (statusFilter !== 'all') {
      filtered = filtered.filter(v => v.status === statusFilter);
    }

    return filtered;
  }, [vouchers, statusFilter]);

  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    toast.success('Voucher code copied to clipboard');
  };

  return (
    <div className="space-y-6">
      <PageTitle title="My Vouchers | Frixel Connect" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">My Vouchers</h2>
          <p className="text-muted-foreground">View all your purchased internet access codes.</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Tabs defaultValue="all" className="w-full md:w-auto" onValueChange={(val) => setStatusFilter(val as any)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="used">Used</TabsTrigger>
            <TabsTrigger value="expired">Expired</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Package</TableHead>
              <TableHead>Expires</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredVouchers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                  You don't have any vouchers matching the selected filter.
                </TableCell>
              </TableRow>
            ) : (
              filteredVouchers.map((voucher) => (
                <TableRow key={voucher.id} className={cn(voucher.status !== 'active' && 'opacity-70')}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-lg tracking-wider">{voucher.code}</span>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="h-8 w-8" 
                        onClick={() => handleCopy(voucher.code)}
                        title="Copy code"
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
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
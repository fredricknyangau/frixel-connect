import { useState, useMemo } from 'react';
import { Loader2, Ticket } from 'lucide-react';

import { useResellerPayments } from '../../hooks/usePayments';
import { useResellerVouchers } from '../../hooks/useVouchers';
import { PaymentStatus } from '../../types/payments';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatKES, formatNairobiDate } from '../../lib/utils';

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '../../components/ui/tooltip';

export default function ResellerPaymentsPage() {
  const { data: payments, isLoading } = useResellerPayments();
  const { data: vouchers } = useResellerVouchers();
  

  const [statusFilter, setStatusFilter] = useState<PaymentStatus | 'all'>('all');

  const filteredPayments = useMemo(() => {
    if (!payments) return [];
    let filtered = [...payments].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    if (statusFilter !== 'all') {
      filtered = filtered.filter(p => p.status === statusFilter);
    }

    return filtered;
  }, [payments, statusFilter]);

  const getVoucherForPayment = (paymentId: string) => vouchers?.find(v => v.payment_id === paymentId);

  return (
    <div className="space-y-6">
      <PageTitle title="Payments | ZealSync Reseller" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Customer Payments</h2>
          <p className="text-muted-foreground">View payments made by your customers.</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Tabs defaultValue="all" className="w-full md:w-auto" onValueChange={(val) => setStatusFilter(val as any)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="pending">Pending</TabsTrigger>
            <TabsTrigger value="confirmed">Confirmed</TabsTrigger>
            <TabsTrigger value="failed">Failed</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer Phone</TableHead>
              <TableHead>Package</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Txn Code</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Voucher</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredPayments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  No payments found matching the selected filter.
                </TableCell>
              </TableRow>
            ) : (
              filteredPayments.map((payment) => {
                const voucher = getVoucherForPayment(payment.id);

                return (
                  <TableRow key={payment.id}>
                    <TableCell className="font-medium">{payment.phone_number}</TableCell>
                    <TableCell>{payment.package_name || 'Unknown'}</TableCell>
                    <TableCell>{formatKES(payment.amount_kes)}</TableCell>
                    <TableCell>
                      {payment.mpesa_receipt_number ? (
                        <span className="font-mono text-xs font-semibold">{payment.mpesa_receipt_number}</span>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground whitespace-nowrap">
                      {formatNairobiDate(payment.created_at)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={payment.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      {payment.status === 'confirmed' && voucher ? (
                        <div className="flex items-center justify-end gap-2">
                          <Tooltip>
                            <TooltipTrigger render={<div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted text-xs font-mono font-medium cursor-help" />}>
                                <Ticket className="h-3.5 w-3.5 text-muted-foreground" />
                                {voucher.code}
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Voucher Status: <span className="capitalize font-medium">{voucher.status}</span></p>
                              {voucher.status === 'active' && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Expires: {formatNairobiDate(voucher.expires_at)}
                                </p>
                              )}
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

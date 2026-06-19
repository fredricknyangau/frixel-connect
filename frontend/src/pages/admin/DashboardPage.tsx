import { useNavigate } from 'react-router-dom';
import { parseISO, isSameDay, isSameMonth } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';
import { AlertCircle } from 'lucide-react';
import { useAdminPayments } from '../../hooks/usePayments';
import { useAdminVouchers } from '../../hooks/useVouchers';
import { useAdminCustomers } from '../../hooks/useUsers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { EmptyState } from '../../components/shared/EmptyState';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Skeleton } from '../../components/ui/skeleton';

const NAIROBI_TZ = 'Africa/Nairobi';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: payments, isLoading: loadingPayments, error: errorPayments } = useAdminPayments();
  const { data: vouchers, isLoading: loadingVouchers, error: errorVouchers } = useAdminVouchers();
  const { data: customers, isLoading: loadingCustomers, error: errorCustomers } = useAdminCustomers();
  

  const isLoading = loadingPayments || loadingVouchers || loadingCustomers;
  const isError = errorPayments || errorVouchers || errorCustomers;

  if (isError) {
    return (
      <div className="p-4">
        <PageTitle title="Dashboard | ZealSync Admin" />
        <EmptyState
          icon={AlertCircle}
          title="Failed to load dashboard"
          description="There was an error fetching the dashboard data. Please try again."
        />
      </div>
    );
  }

  // Compute stats
  const now = new Date();
  const nowNairobi = toZonedTime(now, NAIROBI_TZ);

  let totalRevenueToday = 0;
  let totalRevenue = 0;
  let activeVouchersCount = 0;
  let totalCustomersCount = customers?.length || 0;
  let paymentsThisMonth = 0;

  if (payments) {
    payments.forEach(payment => {
      if (payment.status === 'confirmed') {
        const amount = Number(payment.amount_kes) || 0;
        totalRevenue += amount;
        
        const paymentDateNairobi = toZonedTime(parseISO(payment.created_at), NAIROBI_TZ);
        if (isSameDay(paymentDateNairobi, nowNairobi)) {
          totalRevenueToday += amount;
        }
        if (isSameMonth(paymentDateNairobi, nowNairobi)) {
          paymentsThisMonth += 1;
        }
      }
    });
  }

  if (vouchers) {
    activeVouchersCount = vouchers.filter(v => v.status === 'active').length;
  }

  const recentPayments = payments ? [...payments].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 10) : [];
  const recentVouchers = vouchers ? [...vouchers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 10) : [];

  const getCustomerPhone = (customerId: string) => customers?.find(c => c.id === customerId)?.phone || 'Unknown';

  return (
    <div className="space-y-6">
      <PageTitle title="Dashboard | ZealSync Admin" />

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-24" /> : <div className="text-2xl font-bold">{formatKES(totalRevenue)}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue Today</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-24" /> : <div className="text-2xl font-bold">{formatKES(totalRevenueToday)}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Vouchers</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-16" /> : <div className="text-2xl font-bold">{activeVouchersCount}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Customers</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-16" /> : <div className="text-2xl font-bold">{totalCustomersCount}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Payments This Month</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-16" /> : <div className="text-2xl font-bold">{paymentsThisMonth}</div>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Payments</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Package</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-20 rounded-full" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    </TableRow>
                  ))
                ) : recentPayments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-6">No recent payments</TableCell>
                  </TableRow>
                ) : (
                  recentPayments.map(payment => (
                    <TableRow 
                      key={payment.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/admin/payments')}
                    >
                      <TableCell className="font-medium">{payment.phone_number}</TableCell>
                      <TableCell>{payment.package_name || 'Unknown'}</TableCell>
                      <TableCell>{formatKES(payment.amount_kes)}</TableCell>
                      <TableCell><StatusBadge status={payment.status} /></TableCell>
                      <TableCell className="text-muted-foreground">{formatNairobiDate(payment.created_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Vouchers</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Customer</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-6 w-16 rounded-full" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    </TableRow>
                  ))
                ) : recentVouchers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground py-6">No recent vouchers</TableCell>
                  </TableRow>
                ) : (
                  recentVouchers.map(voucher => (
                    <TableRow 
                      key={voucher.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/admin/vouchers')}
                    >
                      <TableCell className="font-mono font-medium">{voucher.code}</TableCell>
                      <TableCell><StatusBadge status={voucher.status} /></TableCell>
                      <TableCell className="text-muted-foreground">{formatNairobiDate(voucher.expires_at)}</TableCell>
                      <TableCell>{getCustomerPhone(voucher.customer_id)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
import { useNavigate } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';
import { useResellerPayments } from '../../hooks/usePayments';
import { useResellerVouchers } from '../../hooks/useVouchers';
import { useResellerCustomers } from '../../hooks/useUsers';
import { usePackages } from '../../hooks/usePackages';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { EmptyState } from '../../components/shared/EmptyState';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Skeleton } from '../../components/ui/skeleton';

const COMMISSION_RATE = 0.15;

export default function ResellerDashboard() {
  const navigate = useNavigate();
  const { data: payments, isLoading: loadingPayments, error: errorPayments } = useResellerPayments();
  const { data: vouchers, isLoading: loadingVouchers, error: errorVouchers } = useResellerVouchers();
  const { data: customers, isLoading: loadingCustomers, error: errorCustomers } = useResellerCustomers();
  const { data: packages, isLoading: loadingPackages } = usePackages();

  const isLoading = loadingPayments || loadingVouchers || loadingCustomers || loadingPackages;
  const isError = errorPayments || errorVouchers || errorCustomers;

  if (isError) {
    return (
      <div className="p-4">
        <PageTitle title="Dashboard | ZealSync Reseller" />
        <EmptyState
          icon={AlertCircle}
          title="Failed to load dashboard"
          description="There was an error fetching the dashboard data. Please try again."
        />
      </div>
    );
  }

  let totalRevenue = 0;
  let activeVouchersCount = 0;
  let activeCustomersCount = 0;

  if (payments) {
    totalRevenue = payments
      .filter(p => p.status === 'confirmed')
      .reduce((sum, p) => sum + p.amount_kes, 0);
  }

  if (vouchers) {
    activeVouchersCount = vouchers.filter(v => v.status === 'active').length;
  }

  if (customers) {
    activeCustomersCount = customers.filter(c => c.is_active).length;
  }

  const estimatedCommission = totalRevenue * COMMISSION_RATE;

  const recentPayments = payments ? [...payments].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5) : [];
  const recentCustomers = customers ? [...customers].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 5) : [];

  const getPackageName = (packageId: string) => packages?.find(p => p.id === packageId)?.name || 'Unknown';

  return (
    <div className="space-y-6">
      <PageTitle title="Dashboard | ZealSync Reseller" />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Estimated Commission</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-24" /> : <div className="text-2xl font-bold text-primary">{formatKES(estimatedCommission)}</div>}
            <p className="text-xs text-muted-foreground mt-1">Based on 15% rate</p>
          </CardContent>
        </Card>
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
            <CardTitle className="text-sm font-medium">Active Customers</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? <Skeleton className="h-7 w-16" /> : <div className="text-2xl font-bold">{activeCustomersCount}</div>}
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
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Customers</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Phone</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Joined</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    </TableRow>
                  ))
                ) : recentCustomers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground py-6">No customers yet</TableCell>
                  </TableRow>
                ) : (
                  recentCustomers.map(customer => (
                    <TableRow 
                      key={customer.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/reseller/customers')}
                    >
                      <TableCell className="font-medium">{customer.phone}</TableCell>
                      <TableCell>{customer.email}</TableCell>
                      <TableCell className="text-muted-foreground">{formatNairobiDate(customer.created_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

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
                    </TableRow>
                  ))
                ) : recentPayments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground py-6">No recent payments</TableCell>
                  </TableRow>
                ) : (
                  recentPayments.map(payment => (
                    <TableRow 
                      key={payment.id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/reseller/payments')}
                    >
                      <TableCell className="font-medium">{payment.phone_number}</TableCell>
                      <TableCell>{getPackageName(payment.package_id)}</TableCell>
                      <TableCell>{formatKES(payment.amount_kes)}</TableCell>
                      <TableCell><StatusBadge status={payment.status} /></TableCell>
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

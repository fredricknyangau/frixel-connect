import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { parseISO, isSameDay, isSameMonth } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';
import { AlertCircle, X } from 'lucide-react';
import { useAdminPayments } from '../../hooks/usePayments';
import { useAdminVouchers } from '../../hooks/useVouchers';
import { useAdminCustomers } from '../../hooks/useUsers';
import { usePackages } from '../../hooks/usePackages';
import { useRouterSummary } from '../../hooks/useRouterSummary';
import { useTenantMe } from '../../hooks/useTenant';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { EmptyState } from '../../components/shared/EmptyState';
import { SetupChecklist, type ChecklistItem } from '../../components/admin/SetupChecklist';
import { RouterStatusWidget } from '../../components/admin/RouterStatusWidget';
import { TestPaymentGuideDialog } from '../../components/admin/TestPaymentGuideDialog';
import { formatKES, formatNairobiDate } from '../../lib/utils';
import { isOnboardingIncomplete } from '../../lib/onboarding';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Skeleton } from '../../components/ui/skeleton';
import { Button } from '../../components/ui/button';

const NAIROBI_TZ = 'Africa/Nairobi';
const FIRST_RUN_BANNER_KEY = 'Frixel Connect_first_run_banner_dismissed';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: tenant } = useTenantMe();
  const { data: packages, isLoading: loadingPackages } = usePackages();
  const { routers, hasOnlineRouter, isLoading: loadingRouters } = useRouterSummary();

  const [onboardingBannerDismissed, setOnboardingBannerDismissed] = useState(
    () => sessionStorage.getItem('Frixel Connect_onboarding_banner_dismissed') === 'true',
  );
  const [firstRunBannerDismissed, setFirstRunBannerDismissed] = useState(
    () => localStorage.getItem(FIRST_RUN_BANNER_KEY) === 'true',
  );
  const [testPaymentGuideOpen, setTestPaymentGuideOpen] = useState(false);

  const showOnboardingBanner = isOnboardingIncomplete() && !onboardingBannerDismissed;

  const { data: payments, isLoading: loadingPayments, error: errorPayments } = useAdminPayments();
  const { data: vouchers, isLoading: loadingVouchers, error: errorVouchers } = useAdminVouchers();
  const { data: customers, isLoading: loadingCustomers, error: errorCustomers } = useAdminCustomers();

  const isLoading = loadingPayments || loadingVouchers || loadingCustomers || loadingPackages || loadingRouters;
  const isError = errorPayments || errorVouchers || errorCustomers;

  const confirmedPaymentCount =
    payments?.filter((p) => p.status === 'confirmed').length ?? 0;
  const isFirstRun = !isLoading && confirmedPaymentCount === 0;

  const hasPackages = (packages?.length ?? 0) > 0;
  const hasAnyPayment = (payments?.length ?? 0) > 0;
  const hasCustomers =
    (customers?.filter((c) => c.role === 'customer').length ?? 0) > 0;

  const showFirstRunBanner = isFirstRun && !firstRunBannerDismissed;

  const checklistItems: ChecklistItem[] = [
    {
      id: 'packages',
      title: 'Create a package',
      description: 'Define what your customers buy-speed, duration, and price.',
      done: hasPackages,
      ctaLabel: 'Add package →',
      ctaHref: '/admin/packages',
    },
    {
      id: 'router',
      title: 'Connect your MikroTik router',
      description: 'Paste one command in your router terminal. Done in 60 seconds.',
      done: hasOnlineRouter,
      ctaLabel: 'Connect router →',
      ctaHref: '/admin/onboarding/router',
    },
    {
      id: 'payment',
      title: 'Test a payment',
      description: 'Use the Daraja sandbox to send a test M-Pesa payment and see it appear here.',
      done: hasAnyPayment,
      ctaLabel: 'View test guide →',
      onCtaClick: () => setTestPaymentGuideOpen(true),
    },
    {
      id: 'customer',
      title: 'Add your first customer',
      description:
        'Create a customer account manually or share your hotspot portal link for self-registration.',
      done: hasCustomers,
      ctaLabel: 'Add customer →',
      ctaHref: '/admin/customers',
    },
  ];

  if (isError) {
    return (
      <div className="p-4">
        <PageTitle title="Dashboard | Frixel Connect Admin" />
        <EmptyState
          icon={AlertCircle}
          title="Failed to load dashboard"
          description="There was an error fetching the dashboard data. Please try again."
        />
      </div>
    );
  }

  const now = new Date();
  const nowNairobi = toZonedTime(now, NAIROBI_TZ);

  let totalRevenueToday = 0;
  let totalRevenue = 0;
  let activeVouchersCount = 0;
  const totalCustomersCount = customers?.length || 0;
  let paymentsThisMonth = 0;

  if (payments) {
    payments.forEach((payment) => {
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
    activeVouchersCount = vouchers.filter((v) => v.status === 'active').length;
  }

  const recentPayments = payments
    ? [...payments]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 10)
    : [];
  const recentVouchers = vouchers
    ? [...vouchers]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 10)
    : [];

  const getCustomerPhone = (customerId: string) =>
    customers?.find((c) => c.id === customerId)?.phone || 'Unknown';

  return (
    <div className="space-y-6">
      <PageTitle title="Dashboard | Frixel Connect Admin" />

      {showOnboardingBanner && (
        <div className="flex flex-col gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-medium">Complete your setup to start accepting payments →</p>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => navigate('/admin/onboarding')}>
              Continue setup
            </Button>
            <button
              type="button"
              onClick={() => {
                sessionStorage.setItem('Frixel Connect_onboarding_banner_dismissed', 'true');
                setOnboardingBannerDismissed(true);
              }}
              className="rounded-md p-1 text-muted-foreground hover:text-foreground"
              aria-label="Dismiss banner"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {showFirstRunBanner && (
        <div className="relative rounded-lg border border-teal-500/20 border-l-4 border-l-teal-500 bg-teal-500/10 p-4 pr-12">
          <button
            type="button"
            onClick={() => {
              localStorage.setItem(FIRST_RUN_BANNER_KEY, 'true');
              setFirstRunBannerDismissed(true);
            }}
            className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:text-foreground"
            aria-label="Dismiss welcome banner"
          >
            <X className="h-4 w-4" />
          </button>
          <h2 className="text-lg font-semibold">
            Welcome to Frixel Connect, {tenant?.business_name ?? 'there'}!
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            You&apos;re set up. Here&apos;s what to do first to start accepting your first M-Pesa
            payment.
          </p>
        </div>
      )}

      {isFirstRun && (
        <section aria-label="Setup checklist">
          <SetupChecklist items={checklistItems} />
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-7 w-24" />
                ) : (
                  <div className="text-2xl font-bold">{formatKES(totalRevenue)}</div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Revenue Today</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-7 w-24" />
                ) : (
                  <div className="text-2xl font-bold">{formatKES(totalRevenueToday)}</div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Vouchers</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <div className="text-2xl font-bold">{activeVouchersCount}</div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Customers</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <div className="text-2xl font-bold">{totalCustomersCount}</div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Payments This Month</CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-7 w-16" />
                ) : (
                  <div className="text-2xl font-bold">{paymentsThisMonth}</div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>

        <RouterStatusWidget routers={routers} isLoading={loadingRouters} />
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
                      <TableCell>
                        <Skeleton className="h-4 w-24" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-20" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-16" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-6 w-20 rounded-full" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-28" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : recentPayments.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      No recent payments
                    </TableCell>
                  </TableRow>
                ) : (
                  recentPayments.map((payment) => (
                    <TableRow
                      key={payment.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/admin/payments')}
                    >
                      <TableCell className="font-medium">{payment.phone_number}</TableCell>
                      <TableCell>{payment.package_name || 'Unknown'}</TableCell>
                      <TableCell>{formatKES(payment.amount_kes)}</TableCell>
                      <TableCell>
                        <StatusBadge status={payment.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatNairobiDate(payment.created_at)}
                      </TableCell>
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
                      <TableCell>
                        <Skeleton className="h-4 w-20" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-6 w-16 rounded-full" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-28" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-24" />
                      </TableCell>
                    </TableRow>
                  ))
                ) : recentVouchers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                      No recent vouchers
                    </TableCell>
                  </TableRow>
                ) : (
                  recentVouchers.map((voucher) => (
                    <TableRow
                      key={voucher.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate('/admin/vouchers')}
                    >
                      <TableCell className="font-mono font-medium">{voucher.code}</TableCell>
                      <TableCell>
                        <StatusBadge status={voucher.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatNairobiDate(voucher.expires_at)}
                      </TableCell>
                      <TableCell>{getCustomerPhone(voucher.customer_id)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <TestPaymentGuideDialog open={testPaymentGuideOpen} onOpenChange={setTestPaymentGuideOpen} />
    </div>
  );
}

import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Ticket, Wifi, Activity } from 'lucide-react';

import { useCustomerVouchers } from '../../hooks/useVouchers';
import { useCustomerSessions } from '../../hooks/useSessions';
import { usePackages } from '../../hooks/usePackages';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatBytes, formatNairobiDate } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { StatusBadge } from '../../components/shared/StatusBadge';

export default function CustomerDashboard() {
  const navigate = useNavigate();
  const { data: vouchers, isLoading: loadingVouchers } = useCustomerVouchers();
  const { data: sessions, isLoading: loadingSessions } = useCustomerSessions();
  const { data: packages } = usePackages();

  const activeVouchers = vouchers?.filter(v => v.status === 'active') || [];
  
  // Calculate total data usage from all sessions
  const totalBytesDownloaded = sessions?.reduce((sum, s) => sum + s.bytes_downloaded, 0) || 0;
  const totalBytesUploaded = sessions?.reduce((sum, s) => sum + s.bytes_uploaded, 0) || 0;
  const totalDataUsage = totalBytesDownloaded + totalBytesUploaded;

  const getPackageName = (packageId: string) => packages?.find(p => p.id === packageId)?.name || 'Unknown';

  const recentSessions = sessions ? [...sessions].sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()).slice(0, 3) : [];

  return (
    <div className="space-y-6">
      <PageTitle title="Dashboard | ZealSync" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Welcome to ZealSync</h2>
          <p className="text-muted-foreground">Manage your internet access and view usage.</p>
        </div>
        <Button onClick={() => navigate('/customer/buy')} size="lg" className="w-full md:w-auto">
          <ShoppingCart className="mr-2 h-5 w-5" />
          Buy New Package
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Vouchers</CardTitle>
            <Ticket className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loadingVouchers ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <div className="text-2xl font-bold">{activeVouchers.length}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Ready to use</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Data Usage</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loadingSessions ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <div className="text-2xl font-bold text-primary">{formatBytes(totalDataUsage)}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Lifetime consumption</p>
          </CardContent>
        </Card>

        <Card className="md:col-span-2 lg:col-span-1 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Quick Connect</CardTitle>
            <Wifi className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            {activeVouchers.length > 0 ? (
              <div className="space-y-2 mt-1">
                <div className="text-sm font-medium">Your latest code:</div>
                <div className="flex items-center justify-between bg-background p-2 rounded-md border font-mono text-lg font-bold">
                  {activeVouchers[0].code}
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => {
                      navigator.clipboard.writeText(activeVouchers[0].code);
                    }}
                  >
                    Copy
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground mt-2">
                You don't have any active vouchers. Buy a package to get connected.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Your Vouchers</CardTitle>
            <CardDescription>Recently purchased access codes.</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingVouchers ? (
              <div className="space-y-4">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : !vouchers || vouchers.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                No vouchers found.
              </div>
            ) : (
              <div className="space-y-4">
                {vouchers.slice(0, 3).map(voucher => (
                  <div key={voucher.id} className="flex items-center justify-between p-3 rounded-lg border">
                    <div>
                      <div className="font-mono font-bold text-lg">{voucher.code}</div>
                      <div className="text-xs text-muted-foreground">{getPackageName(voucher.package_id)}</div>
                    </div>
                    <div className="text-right">
                      <StatusBadge status={voucher.status} />
                      <div className="text-xs text-muted-foreground mt-1">
                        Exp: {formatNairobiDate(voucher.expires_at)}
                      </div>
                    </div>
                  </div>
                ))}
                {vouchers.length > 3 && (
                  <Button variant="outline" className="w-full" onClick={() => navigate('/customer/vouchers')}>
                    View All Vouchers
                  </Button>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Sessions</CardTitle>
            <CardDescription>Your latest device connections.</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingSessions ? (
              <div className="space-y-4">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : recentSessions.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                No active sessions found.
              </div>
            ) : (
              <div className="space-y-4">
                {recentSessions.map(session => (
                  <div key={session.id} className="flex flex-col gap-1 p-3 rounded-lg border">
                    <div className="flex justify-between items-start">
                      <div className="font-mono text-sm">{session.mac_address || 'Unknown Device'}</div>
                      <div className="text-xs font-medium px-2 py-0.5 rounded bg-muted">
                        {session.ended_at ? 'Closed' : 'Active'}
                      </div>
                    </div>
                    <div className="flex justify-between items-center text-sm mt-1">
                      <span className="text-muted-foreground">{formatNairobiDate(session.started_at)}</span>
                      <span className="font-medium text-primary">
                        {formatBytes(session.bytes_downloaded + session.bytes_uploaded)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
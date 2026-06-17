import { useState, useMemo } from 'react';
import { Search, Loader2 } from 'lucide-react';

import { useAdminCustomers } from '../../hooks/useUsers';
import { useAdminPayments } from '../../hooks/usePayments';
import { useAdminVouchers } from '../../hooks/useVouchers';
import { usePackages } from '../../hooks/usePackages';
import { UserRole } from '../../types/auth';
import { User } from '../../types/users';
import { Payment } from '../../types/payments';
import { Voucher } from '../../types/vouchers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatKES, formatNairobiDate } from '../../lib/utils';

import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../../components/ui/sheet';

export default function CustomersPage() {
  const { data: users, isLoading } = useAdminCustomers();
  const { data: payments } = useAdminPayments();
  const { data: vouchers } = useAdminVouchers();
  const { data: packages } = usePackages();

  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  const filteredUsers = useMemo(() => {
    if (!users) return [];
    let filtered = users;

    if (roleFilter !== 'all') {
      filtered = filtered.filter(u => u.role === roleFilter);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(u => 
        u.email.toLowerCase().includes(q) || 
        u.phone.includes(q)
      );
    }

    return filtered;
  }, [users, roleFilter, searchQuery]);

  const handleRowClick = (user: User) => {
    setSelectedUser(user);
    setIsSheetOpen(true);
  };

  const selectedUserPayments = useMemo(() => {
    if (!selectedUser || !payments) return [];
    return payments
      .filter(p => p.customer_id === selectedUser.id)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5);
  }, [selectedUser, payments]);

  const selectedUserVouchers = useMemo(() => {
    if (!selectedUser || !vouchers) return [];
    return vouchers.filter(v => v.customer_id === selectedUser.id && v.status === 'active');
  }, [selectedUser, vouchers]);

  const getPackageName = (packageId: string) => packages?.find(p => p.id === packageId)?.name || 'Unknown';

  return (
    <div className="space-y-6">
      <PageTitle title="Users & Customers | ZealSync Admin" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Users</h2>
          <p className="text-muted-foreground">Manage your customers, resellers, and admins.</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Tabs defaultValue="all" className="w-full md:w-auto" onValueChange={(val) => setRoleFilter(val as any)}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="customer">Customer</TabsTrigger>
            <TabsTrigger value="reseller">Reseller</TabsTrigger>
            <TabsTrigger value="admin">Admin</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full md:w-72">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            placeholder="Search email or phone..." 
            className="pl-8" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="rounded-md border bg-background overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Phone</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Reseller</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Joined</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No users found matching your search.
                </TableCell>
              </TableRow>
            ) : (
              filteredUsers.map((user: User) => (
                <TableRow 
                  key={user.id} 
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => handleRowClick(user)}
                >
                  <TableCell className="font-medium">{user.phone}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell className="capitalize">{user.role}</TableCell>
                  <TableCell>
                    {user.reseller_id ? (
                      <span className="text-muted-foreground text-sm truncate max-w-[100px] inline-block" title={user.reseller_id}>
                        {user.reseller_id.substring(0, 8)}...
                      </span>
                    ) : '-'}
                  </TableCell>
                  <TableCell>
                    {user.is_active ? (
                      <Badge variant="outline" className="border-transparent bg-green-100 text-green-800">Active</Badge>
                    ) : (
                      <Badge variant="outline" className="bg-gray-100 text-gray-800 border-transparent">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatNairobiDate(user.created_at)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
        <SheetContent side="right" className="w-full sm:w-[400px] sm:max-w-none flex flex-col p-0">
          {selectedUser && (
            <>
              <div className="p-6 pb-4 border-b">
                <SheetHeader>
                  <SheetTitle className="text-xl">{selectedUser.phone}</SheetTitle>
                  <SheetDescription>{selectedUser.email}</SheetDescription>
                </SheetHeader>
                <div className="mt-4 flex items-center gap-2">
                  <Badge variant="secondary" className="capitalize">{selectedUser.role}</Badge>
                  {selectedUser.is_active ? (
                    <Badge variant="outline" className="border-transparent bg-green-100 text-green-800">Active</Badge>
                  ) : (
                    <Badge variant="outline" className="bg-gray-100 text-gray-800 border-transparent">Inactive</Badge>
                  )}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-8">
                {/* Active Vouchers */}
                <div>
                  <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Active Vouchers</h3>
                  {selectedUserVouchers.length > 0 ? (
                    <div className="space-y-3">
                      {selectedUserVouchers.map((voucher: Voucher) => (
                        <div key={voucher.id} className="p-3 rounded-lg border bg-card flex justify-between items-center">
                          <div>
                            <div className="font-mono font-medium">{voucher.code}</div>
                            <div className="text-xs text-muted-foreground mt-1">
                              Expires: {formatNairobiDate(voucher.expires_at)}
                            </div>
                          </div>
                          <Badge variant="outline" className="border-primary text-primary">
                            {getPackageName(voucher.package_id)}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No active vouchers.</p>
                  )}
                </div>

                {/* Recent Payments */}
                <div>
                  <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Recent Payments</h3>
                  {selectedUserPayments.length > 0 ? (
                    <div className="space-y-3">
                      {selectedUserPayments.map((payment: Payment) => (
                        <div key={payment.id} className="p-3 rounded-lg border bg-card flex justify-between items-start">
                          <div>
                            <div className="font-medium">{formatKES(payment.amount_kes)}</div>
                            <div className="text-xs text-muted-foreground mt-1">
                              {formatNairobiDate(payment.created_at)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {getPackageName(payment.package_id)}
                            </div>
                          </div>
                          <StatusBadge status={payment.status} />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No recent payments.</p>
                  )}
                </div>
                
                {/* Meta details */}
                <div className="pt-4 border-t">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="text-muted-foreground mb-1">Joined</div>
                      <div>{formatNairobiDate(selectedUser.created_at)}</div>
                    </div>
                    {selectedUser.reseller_id && (
                      <div>
                        <div className="text-muted-foreground mb-1">Reseller ID</div>
                        <div className="truncate" title={selectedUser.reseller_id}>{selectedUser.reseller_id.substring(0, 8)}...</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
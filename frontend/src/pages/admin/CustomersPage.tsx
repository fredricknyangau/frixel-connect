import { useState, useMemo, useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Search, Loader2, Plus, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { 
  useAdminCustomers, 
  useAdminCreateUser, 
  useAdminUpdateUser, 
  useAdminDeleteUser 
} from '../../hooks/useUsers';
import { useAdminPayments } from '../../hooks/usePayments';
import { useAdminVouchers } from '../../hooks/useVouchers';
import { usePackages } from '../../hooks/usePackages';
import { useRouters } from '../../hooks/useRouters';
import { UserRole } from '../../types/auth';
import { User } from '../../types/users';
import { Payment } from '../../types/payments';
import { Voucher } from '../../types/vouchers';
import { PageTitle } from '../../components/shared/PageTitle';
import { StatusBadge } from '../../components/shared/StatusBadge';
import { formatKES, formatNairobiDate, cn } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../../components/ui/sheet';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../../components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';

const userSchema = z.object({
  email: z.string().email('Invalid email address'),
  phone: z.string().min(1, 'Phone is required'),
  password: z.string().min(8, 'Password must be at least 8 characters').optional().or(z.literal('')),
  role: z.enum(['admin', 'reseller', 'customer']),
  router_id: z.string().optional().or(z.literal('')),
});

type UserFormValues = z.infer<typeof userSchema>;

export default function CustomersPage() {
  const { data: users, isLoading } = useAdminCustomers();
  const { data: payments } = useAdminPayments();
  const { data: vouchers } = useAdminVouchers();
  const { data: packages } = usePackages();
  const { data: routers } = useRouters();

  const createUser = useAdminCreateUser();
  const updateUser = useAdminUpdateUser();
  const deactivateUser = useAdminDeleteUser();

  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<string | null>(null);

  const { register, handleSubmit, reset, control, watch, formState: { errors, isSubmitting } } = useForm<UserFormValues>({
    resolver: zodResolver(userSchema),
    defaultValues: { role: 'customer', router_id: '' }
  });

  const selectedRole = watch('role') || 'customer';

  useEffect(() => {
    if (editingUser) {
      reset({
        email: editingUser.email,
        phone: editingUser.phone,
        role: editingUser.role,
        password: '',
        router_id: (editingUser as any).router_id || '',
      });
    } else {
      reset({ email: '', phone: '', password: '', role: 'customer', router_id: '' });
    }
  }, [editingUser, reset]);

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

  const handleOpenDialog = (e?: React.MouseEvent, user?: User) => {
    if (e) e.stopPropagation();
    setEditingUser(user || null);
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingUser(null);
  };

  const onSubmit = async (data: UserFormValues) => {
    try {
      if (editingUser) {
        const updateData: any = { email: data.email, phone: data.phone, role: data.role };
        if (data.password) {
          updateData.password = data.password;
        }
        if (data.role === 'customer') {
          updateData.router_id = data.router_id || null;
        }
        await updateUser.mutateAsync({ id: editingUser.id, data: updateData });
        toast.success('User updated successfully');
      } else {
        if (!data.password) {
          toast.error('Password is required for new users');
          return;
        }
        await createUser.mutateAsync(data as any);
        toast.success('User created successfully');
      }
      handleCloseDialog();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to save user');
    }
  };

  const handleDeactivate = async () => {
    if (deletingUserId) {
      try {
        await deactivateUser.mutateAsync(deletingUserId);
        toast.success('User deactivated');
      } catch (error) {
        toast.error('Failed to deactivate user');
      } finally {
        setIsDeleteDialogOpen(false);
        setDeletingUserId(null);
      }
    }
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
        <Button onClick={(e) => handleOpenDialog(e)}>
          <Plus className="mr-2 h-4 w-4" /> Add User
        </Button>
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
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
                </TableCell>
              </TableRow>
            ) : filteredUsers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  No users found matching your search.
                </TableCell>
              </TableRow>
            ) : (
              filteredUsers.map((user: User) => (
                <TableRow 
                  key={user.id} 
                  className={cn("cursor-pointer hover:bg-muted/50", !user.is_active && 'text-muted-foreground opacity-60')}
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
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-2">
                      <Button variant="ghost" size="icon" onClick={(e) => handleOpenDialog(e, user)} disabled={!user.is_active}>
                        <Pencil className="h-4 w-4" />
                        <span className="sr-only">Edit</span>
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon" 
                        className="text-destructive hover:text-destructive/90 hover:bg-destructive/10"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeletingUserId(user.id);
                          setIsDeleteDialogOpen(true);
                        }}
                        disabled={!user.is_active}
                      >
                        <Trash2 className="h-4 w-4" />
                        <span className="sr-only">Deactivate</span>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Edit User' : 'Add User'}</DialogTitle>
            <DialogDescription>
              {editingUser ? 'Update user profile and role.' : 'Create a new user. Default role is customer.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input id="email" type="email" placeholder="e.g. hello@example.com" {...register('email')} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input id="phone" placeholder="e.g. 0712345678" {...register('phone')} />
              {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password {editingUser && '(Leave empty to keep current)'}</Label>
              <Input id="password" type="password" placeholder="Min 8 characters" {...register('password')} />
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Controller
                name="role"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="customer">Customer</SelectItem>
                      <SelectItem value="reseller">Reseller</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.role && <p className="text-sm text-destructive">{errors.role.message}</p>}
            </div>

            {selectedRole === 'customer' && (
              <div className="space-y-2">
                <Label htmlFor="router_id">Site/Router Assignment</Label>
                <Controller
                  name="router_id"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value || ''} onValueChange={field.onChange}>
                      <SelectTrigger>
                        <SelectValue placeholder={routers?.length === 0 ? "No routers connected" : "Select a router site"} />
                      </SelectTrigger>
                      <SelectContent>
                        {routers?.map((router) => (
                          <SelectItem key={router.id} value={router.id}>
                            {router.name} ({router.site_name})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {routers?.length === 0 && (
                  <p className="text-xs text-amber-500">Please connect a router first in Routers management.</p>
                )}
                {errors.router_id && <p className="text-sm text-destructive">{errors.router_id.message}</p>}
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting || createUser.isPending || updateUser.isPending}>
                {isSubmitting || createUser.isPending || updateUser.isPending ? 'Saving...' : 'Save User'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate this user?</AlertDialogTitle>
            <AlertDialogDescription>
              This will disable their access to the system. Their history, payments, and vouchers will be preserved.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeactivate} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
                    {(selectedUser as any).router_id && (
                      <div>
                        <div className="text-muted-foreground mb-1">Router Site</div>
                        <div>
                          {routers?.find(r => r.id === (selectedUser as any).router_id)?.name || 'Unknown'}
                        </div>
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
import { useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, Plus, Search, Eye, EyeOff, Ticket } from 'lucide-react';
import { toast } from 'sonner';

import { useResellerCustomers, useCreateResellerCustomer } from '../../hooks/useUsers';
import { useRouters } from '../../hooks/useRouters';
import { PageTitle } from '../../components/shared/PageTitle';
import { formatNairobiDate } from '../../lib/utils';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import GenerateVoucherDialog from './GenerateVoucherDialog';

const createCustomerSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  router_id: z.string().min(1, 'Please select a router site'),
});

type CreateCustomerFormValues = z.infer<typeof createCustomerSchema>;

export default function MyCustomersPage() {
  const { data: customers, isLoading } = useResellerCustomers();
  const { data: routers } = useRouters();
  const createCustomer = useCreateResellerCustomer();

  const [searchQuery, setSearchQuery] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Voucher dialog states
  const [isVoucherOpen, setIsVoucherOpen] = useState(false);
  const [voucherCustId, setVoucherCustId] = useState<string | null>(null);

  const { register, handleSubmit, reset, control, setError, formState: { errors, isSubmitting } } = useForm<CreateCustomerFormValues>({
    resolver: zodResolver(createCustomerSchema),
    defaultValues: {
      email: '',
      phone: '',
      password: '',
      router_id: '',
    }
  });

  const filteredCustomers = customers?.filter(c => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return c.email.toLowerCase().includes(q) || c.phone.includes(q);
  }) || [];

  const handleOpenDialog = () => {
    reset();
    setIsDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
  };

  const onSubmit = async (data: CreateCustomerFormValues) => {
    try {
      await createCustomer.mutateAsync(data);
      toast.success('Customer created successfully');
      handleCloseDialog();
    } catch (error: any) {
      if (error.response?.status === 409) {
        setError('root', { message: 'This email or phone is already registered.' });
      } else {
        toast.error('Failed to create customer');
      }
    }
  };

  const handleSellPlan = (customerId: string) => {
    setVoucherCustId(customerId);
    setIsVoucherOpen(true);
  };

  return (
    <div className="space-y-6">
      <PageTitle title="My Customers | Frixel Connect Reseller" />

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">My Customers</h2>
          <p className="text-muted-foreground">Manage your WiFi hotspot customers.</p>
        </div>
        <Button onClick={handleOpenDialog}>
          <Plus className="mr-2 h-4 w-4" /> Add Customer
        </Button>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center">
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
              <TableHead>Site</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Joined</TableHead>
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
            ) : filteredCustomers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  No customers found. Add your first customer to get started.
                </TableCell>
              </TableRow>
            ) : (
              filteredCustomers.map((customer) => (
                <TableRow key={customer.id}>
                  <TableCell className="font-medium">{customer.phone}</TableCell>
                  <TableCell>{customer.email}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {routers?.find(r => r.id === (customer as any).router_id)?.site_name || '-'}
                  </TableCell>
                  <TableCell>
                    {customer.is_active ? (
                      <Badge variant="outline" className="border-transparent bg-green-100 text-green-800">Active</Badge>
                    ) : (
                      <Badge variant="outline" className="bg-gray-100 text-gray-800 border-transparent">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatNairobiDate(customer.created_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSellPlan(customer.id)}
                      disabled={!customer.is_active}
                    >
                      <Ticket className="h-4 w-4 mr-1 text-primary" />
                      Sell Plan
                    </Button>
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
            <DialogTitle>Add Customer</DialogTitle>
            <DialogDescription>
              Create a new customer account. They will be automatically linked to you.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="customer@example.com" {...register('email')} />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input id="phone" type="tel" placeholder="0712 345 678" {...register('phone')} />
              {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Initial Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="router_id">Site/Router Assignment</Label>
              <Controller
                name="router_id"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder={routers?.length === 0 ? "No router sites available" : "Select a site"} />
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
                <p className="text-xs text-amber-500">No router sites available. Contact your admin.</p>
              )}
              {errors.router_id && <p className="text-sm text-destructive">{errors.router_id.message}</p>}
            </div>

            {errors.root && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {errors.root.message}
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleCloseDialog}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting || createCustomer.isPending}>
                {isSubmitting || createCustomer.isPending ? 'Creating...' : 'Create Customer'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <GenerateVoucherDialog
        open={isVoucherOpen}
        onOpenChange={setIsVoucherOpen}
        preselectedCustomerId={voucherCustId || undefined}
      />
    </div>
  );
}

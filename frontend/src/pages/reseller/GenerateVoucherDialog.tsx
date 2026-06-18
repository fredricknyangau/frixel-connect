import { useState, useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, CheckCircle2, AlertTriangle, UserPlus, Search } from 'lucide-react';
import { toast } from 'sonner';

import { useResellerCustomers, useCreateResellerCustomer } from '../../hooks/useUsers';
import { usePackages } from '../../hooks/usePackages';
import { useWalletBalance, useGenerateWalletVoucher } from '../../hooks/useWallet';
import { useRouters } from '../../hooks/useRouters';
import { formatKES } from '../../lib/utils';

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Input } from '../../components/ui/input';

const quickCustomerSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  router_id: z.string().min(1, 'Please select a router site'),
});

type QuickCustomerFormValues = z.infer<typeof quickCustomerSchema>;

interface GenerateVoucherDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preselectedCustomerId?: string;
}

export default function GenerateVoucherDialog({
  open,
  onOpenChange,
  preselectedCustomerId,
}: GenerateVoucherDialogProps) {
  const { data: wallet } = useWalletBalance();
  const { data: customers } = useResellerCustomers();
  const { data: packages } = usePackages();
  const { data: routers } = useRouters();
  const generateVoucher = useGenerateWalletVoucher();
  const createCustomer = useCreateResellerCustomer();

  const [step, setStep] = useState(1);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [selectedPackageId, setSelectedPackageId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isQuickAdding, setIsQuickAdding] = useState(false);
  const [generatedVoucher, setGeneratedVoucher] = useState<any>(null);

  const { register, handleSubmit, reset, control, setError, formState: { errors, isSubmitting } } = useForm<QuickCustomerFormValues>({
    resolver: zodResolver(quickCustomerSchema),
    defaultValues: { email: '', phone: '', password: '', router_id: '' }
  });

  // Handle pre-selection
  useEffect(() => {
    if (open) {
      setStep(1);
      setSelectedCustomerId(preselectedCustomerId || '');
      setSelectedPackageId('');
      setSearchQuery('');
      setIsQuickAdding(false);
      setGeneratedVoucher(null);
      reset();
    }
  }, [open, preselectedCustomerId, reset]);

  const filteredCustomers = customers?.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return c.email.toLowerCase().includes(q) || c.phone.includes(q);
  }) || [];

  const handleQuickAdd = async (data: QuickCustomerFormValues) => {
    try {
      const newCust = await createCustomer.mutateAsync(data);
      toast.success('Customer account registered');
      setSelectedCustomerId(newCust.id);
      setIsQuickAdding(false);
      reset();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError('root', { message: 'Phone or email is already registered.' });
      } else {
        toast.error('Failed to register customer');
      }
    }
  };

  const handleNextStep = () => {
    if (!selectedCustomerId) {
      toast.error('Please select or create a customer first.');
      return;
    }
    setStep(2);
  };

  const currentPackage = packages?.find(p => p.id === selectedPackageId);
  const walletBalance = wallet?.balance_kes || 0;
  const packagePrice = currentPackage?.price_kes || 0;
  const balanceAfter = walletBalance - packagePrice;
  const isAffordable = balanceAfter >= 0;

  const handleConfirmGenerate = async () => {
    if (!selectedCustomerId || !selectedPackageId) return;
    if (!isAffordable) {
      toast.error('Insufficient wallet balance to buy this package.');
      return;
    }

    try {
      const response = await generateVoucher.mutateAsync({
        customer_id: selectedCustomerId,
        package_id: selectedPackageId,
      });
      setGeneratedVoucher(response);
      setStep(3);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to debit wallet and generate voucher.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle>Generate Hotspot Voucher</DialogTitle>
          <DialogDescription>
            Fund a new subscriber package directly from your reseller balance.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4 py-2">
            {!isQuickAdding ? (
              <>
                <div className="flex items-center justify-between">
                  <Label>1. Select Subscriber</Label>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-primary"
                    onClick={() => setIsQuickAdding(true)}
                  >
                    <UserPlus className="h-3 w-3 mr-1" /> Quick-add new
                  </Button>
                </div>

                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search phone or email..."
                    className="pl-8"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div className="max-h-[200px] overflow-y-auto border rounded-md divide-y bg-background">
                  {filteredCustomers.length === 0 ? (
                    <div className="p-4 text-center text-sm text-muted-foreground">
                      No subscribers found.
                    </div>
                  ) : (
                    filteredCustomers.map((customer) => (
                      <button
                        key={customer.id}
                        type="button"
                        onClick={() => setSelectedCustomerId(customer.id)}
                        className={`w-full text-left p-3 text-sm transition-colors flex justify-between items-center ${
                          selectedCustomerId === customer.id ? 'bg-primary/10 font-semibold' : 'hover:bg-muted/50'
                        }`}
                      >
                        <div>
                          <div>{customer.phone}</div>
                          <div className="text-xs text-muted-foreground">{customer.email}</div>
                        </div>
                        {selectedCustomerId === customer.id && (
                          <span className="text-xs text-primary font-bold">Selected</span>
                        )}
                      </button>
                    ))
                  )}
                </div>

                <Button className="w-full" onClick={handleNextStep} disabled={!selectedCustomerId}>
                  Continue to Packages
                </Button>
              </>
            ) : (
              <form onSubmit={handleSubmit(handleQuickAdd)} className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-semibold">Quick Register Customer</Label>
                  <button
                    type="button"
                    onClick={() => setIsQuickAdding(false)}
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    Back to search
                  </button>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="quick_email">Email</Label>
                  <Input id="quick_email" type="email" placeholder="customer@example.com" {...register('email')} />
                  {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label htmlFor="quick_phone">Phone</Label>
                  <Input id="quick_phone" type="tel" placeholder="07XXXXXXXX" {...register('phone')} />
                  {errors.phone && <p className="text-xs text-destructive">{errors.phone.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label htmlFor="quick_password">Password</Label>
                  <Input id="quick_password" type="password" placeholder="Min 8 characters" {...register('password')} />
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label htmlFor="quick_router">Router/Site Location</Label>
                  <Controller
                    name="router_id"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger>
                          <SelectValue placeholder={routers?.length === 0 ? "No router sites" : "Select site"} />
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
                  {errors.router_id && <p className="text-xs text-destructive">{errors.router_id.message}</p>}
                </div>

                {errors.root && (
                  <p className="text-xs text-destructive bg-destructive/10 p-2 rounded">{errors.root.message}</p>
                )}

                <Button type="submit" className="w-full mt-2" disabled={isSubmitting || createCustomer.isPending}>
                  {isSubmitting || createCustomer.isPending ? 'Registering...' : 'Register & Select'}
                </Button>
              </form>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>2. Select Package</Label>
              <Select value={selectedPackageId} onValueChange={setSelectedPackageId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a plan" />
                </SelectTrigger>
                <SelectContent>
                  {packages?.filter(p => p.is_active).map((pkg) => (
                    <SelectItem key={pkg.id} value={pkg.id}>
                      {pkg.name} - {formatKES(pkg.price_kes)} ({pkg.duration_days} Days)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedPackageId && currentPackage && (
              <div className="rounded-lg border bg-muted p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Reseller Wallet Balance</span>
                  <span className="font-semibold">{formatKES(walletBalance)}</span>
                </div>
                <div className="flex justify-between border-b pb-2">
                  <span>Package Cost</span>
                  <span className="font-semibold text-destructive">- {formatKES(packagePrice)}</span>
                </div>
                <div className="flex justify-between pt-1">
                  <span>Balance After Debit</span>
                  <span className={`font-bold ${isAffordable ? 'text-green-600' : 'text-red-600'}`}>
                    {formatKES(balanceAfter)}
                  </span>
                </div>
              </div>
            )}

            {!isAffordable && selectedPackageId && (
              <div className="flex items-center gap-2 p-3 rounded-md bg-destructive/10 text-destructive text-xs">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>Insufficient balance. Top up your wallet before generating this voucher.</span>
              </div>
            )}

            <DialogFooter className="flex gap-2 sm:justify-between pt-2">
              <Button type="button" variant="outline" onClick={() => setStep(1)} disabled={generateVoucher.isPending}>
                Back
              </Button>
              <Button
                type="button"
                onClick={handleConfirmGenerate}
                disabled={!selectedPackageId || !isAffordable || generateVoucher.isPending}
              >
                {generateVoucher.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Generating...
                  </>
                ) : (
                  'Confirm & Generate'
                )}
              </Button>
            </DialogFooter>
          </div>
        )}

        {step === 3 && generatedVoucher && (
          <div className="space-y-6 text-center py-4 animate-in fade-in scale-in duration-300">
            <div className="mx-auto h-12 w-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-semibold text-foreground">Voucher Code Created</h3>
              <p className="text-xs text-muted-foreground">
                Voucher debited from wallet and synced with client profile.
              </p>
            </div>

            <div className="border bg-muted p-4 rounded-lg space-y-2 max-w-[280px] mx-auto">
              <div className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
                Access Code
              </div>
              <div className="text-2xl font-mono font-bold tracking-widest text-primary">
                {generatedVoucher.code}
              </div>
              <div className="text-xs text-muted-foreground pt-1">
                Plan: {generatedVoucher.package_name}
              </div>
            </div>

            <Button className="w-full mt-2" onClick={() => onOpenChange(false)}>
              Close Dialog
            </Button>
          </div>
        )}
      </Dialog>
    </Dialog>
  );
}

import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Eye, EyeOff, Loader2, Wifi, Globe } from 'lucide-react';
import { useTenantSignup } from '../../hooks/useTenantSignup';
import { PageTitle } from '../../components/shared/PageTitle';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { cn } from '../../lib/utils';
import type { ServiceType } from '../../lib/onboarding';
import { AxiosError } from 'axios';

// Pricing mirrors landing page tiers-shown live below the tier dropdown.
const tierDetails = {
  starter: { price: 'KES 1,500/mo', customers: 'Up to 100 customers', routers: '1 router' },
  growth: { price: 'KES 2,500/mo', customers: 'Up to 300 customers', routers: '3 routers' },
  scale: { price: 'KES 4,000/mo', customers: 'Up to 700 customers', routers: '10 routers' },
  enterprise: { price: 'KES 6,000/mo', customers: 'Unlimited customers', routers: '50 routers' },
} as const;

const subscriptionTiers = ['starter', 'growth', 'scale', 'enterprise'] as const;

const signupSchema = z.object({
  business_name: z.string().min(2, 'Business name must be at least 2 characters').max(100),
  owner_name: z.string().min(2, 'Your name must be at least 2 characters'),
  owner_email: z.string().email('Enter a valid email address'),
  owner_phone: z
    .string()
    .transform((v) => v.replace(/\s+/g, ''))
    .pipe(
      z.string().regex(/^(?:\+?254|0)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
    ),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  subscription_tier: z.enum(subscriptionTiers),
  service_type: z.enum(['hotspot', 'pppoe']),
});

type SignupFormValues = z.infer<typeof signupSchema>;

function getPasswordStrength(password: string): 0 | 1 | 2 | 3 {
  if (password.length < 8) return 1;
  const hasUpper = /[A-Z]/.test(password);
  const hasNumber = /\d/.test(password);
  if (hasUpper && hasNumber) return 3;
  return 2;
}

function mapApiFieldToFormField(apiField: string): keyof SignupFormValues | null {
  const map: Record<string, keyof SignupFormValues> = {
    business_name: 'business_name',
    owner_email: 'owner_email',
    owner_phone: 'owner_phone',
    password: 'password',
    subscription_tier: 'subscription_tier',
  };
  return map[apiField] ?? null;
}

export default function TenantSignupPage() {
  const [searchParams] = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const signupMutation = useTenantSignup();

  const urlTier = searchParams.get('tier');
  const urlService = searchParams.get('service');
  const defaultTier = subscriptionTiers.includes(urlTier as typeof subscriptionTiers[number])
    ? (urlTier as typeof subscriptionTiers[number])
    : 'growth';
  const defaultService: ServiceType =
    urlService === 'pppoe' ? 'pppoe' : urlService === 'hotspot' ? 'hotspot' : 'hotspot';

  const {
    register,
    handleSubmit,
    control,
    watch,
    setError,
    setValue,
    formState: { errors },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      subscription_tier: defaultTier,
      service_type: defaultService,
    },
  });

  const selectedTier = watch('subscription_tier') || 'growth';
  const selectedService = watch('service_type');
  const passwordValue = watch('password') || '';
  const strength = getPasswordStrength(passwordValue);

  const onSubmit = async (data: SignupFormValues) => {
    try {
      await signupMutation.mutateAsync(data);
    } catch (error) {
      const axiosError = error as AxiosError<{ detail?: string | Array<{ loc: (string | number)[]; msg: string }> }>;
      if (axiosError.response?.status === 409) {
        setError('owner_email', { message: 'An account with this email already exists.' });
        return;
      }
      if (axiosError.response?.status === 422) {
        const detail = axiosError.response.data?.detail;
        if (Array.isArray(detail)) {
          detail.forEach((item) => {
            const field = item.loc[item.loc.length - 1];
            if (typeof field === 'string') {
              const formField = mapApiFieldToFormField(field);
              if (formField) {
                setError(formField, { message: item.msg });
              }
            }
          });
          return;
        }
      }
      setError('root', {
        message: 'Registration failed. Please try again.',
      });
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4 py-10 dark">
      <PageTitle title="Start Your Free Trial | ZealSync" />
      <Card className="w-full max-w-lg border-border/60 shadow-xl">
        <CardHeader className="text-center pb-2">
          <div className="mb-3 flex items-center justify-center gap-2">
            <Wifi className="h-5 w-5 text-primary" />
            <span className="text-lg font-bold text-primary">ZealSync</span>
          </div>
          <CardTitle className="text-2xl">Start your free 30-day pilot</CardTitle>
          <CardDescription>No credit card. Cancel anytime.</CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Service type toggle-pre-selected from ?service= landing page CTA */}
            <div className="space-y-2">
              <Label>What type of ISP are you?</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setValue('service_type', 'hotspot', { shouldValidate: true })}
                  className={cn(
                    'flex flex-col items-center gap-2 rounded-xl border-2 p-4 text-left transition-all',
                    selectedService === 'hotspot'
                      ? 'border-primary ring-2 ring-primary/30 bg-primary/5'
                      : 'border-border hover:border-primary/40',
                  )}
                >
                  <Wifi className={cn('h-6 w-6', selectedService === 'hotspot' ? 'text-primary' : 'text-muted-foreground')} />
                  <div>
                    <p className="text-sm font-semibold">Hotspot WiFi</p>
                    <p className="text-xs text-muted-foreground">Captive portal + vouchers</p>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => setValue('service_type', 'pppoe', { shouldValidate: true })}
                  className={cn(
                    'flex flex-col items-center gap-2 rounded-xl border-2 p-4 text-left transition-all',
                    selectedService === 'pppoe'
                      ? 'border-primary ring-2 ring-primary/30 bg-primary/5'
                      : 'border-border hover:border-primary/40',
                  )}
                >
                  <Globe className={cn('h-6 w-6', selectedService === 'pppoe' ? 'text-primary' : 'text-muted-foreground')} />
                  <div>
                    <p className="text-sm font-semibold">Fiber / PPPoE</p>
                    <p className="text-xs text-muted-foreground">Monthly subscriptions + recurring billing</p>
                  </div>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="business_name">Business / ISP Name</Label>
              <Input
                id="business_name"
                placeholder="e.g. Eastlands Wireless, Mwangi Networks"
                {...register('business_name')}
              />
              {errors.business_name && (
                <p className="text-sm text-destructive">{errors.business_name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="owner_name">Your Name</Label>
              <Input id="owner_name" placeholder="e.g. John Kamau" {...register('owner_name')} />
              {errors.owner_name && (
                <p className="text-sm text-destructive">{errors.owner_name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="owner_email">Email address</Label>
              <Input
                id="owner_email"
                type="email"
                placeholder="you@yourcompany.com"
                {...register('owner_email')}
              />
              {errors.owner_email && (
                <div className="space-y-1">
                  <p className="text-sm text-destructive">{errors.owner_email.message}</p>
                  {errors.owner_email.message?.includes('already exists') && (
                    <Link to="/login" className="text-sm text-primary hover:underline">
                      Sign in instead →
                    </Link>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="owner_phone">Phone number (M-Pesa)</Label>
              <Input
                id="owner_phone"
                type="tel"
                placeholder="0712 345 678"
                {...register('owner_phone')}
              />
              <p className="text-xs text-muted-foreground">
                This number receives your ZealSync billing invoices via M-Pesa
              </p>
              {errors.owner_phone && (
                <p className="text-sm text-destructive">{errors.owner_phone.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
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
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {/* 3-segment strength bar: red / amber / green */}
              <div className="flex gap-1 pt-1">
                {[1, 2, 3].map((segment) => (
                  <div
                    key={segment}
                    className={cn(
                      'h-1.5 flex-1 rounded-full transition-colors',
                      strength >= segment
                        ? strength === 1
                          ? 'bg-red-500'
                          : strength === 2
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                        : 'bg-muted',
                    )}
                  />
                ))}
              </div>
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="subscription_tier">Subscription tier</Label>
              <Controller
                control={control}
                name="subscription_tier"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="subscription_tier">
                      <SelectValue placeholder="Select a tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">Starter</SelectItem>
                      <SelectItem value="growth">Growth (Recommended)</SelectItem>
                      <SelectItem value="scale">Scale</SelectItem>
                      <SelectItem value="enterprise">Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              <div className="rounded-lg border bg-muted/40 p-3 text-sm space-y-1">
                <div className="flex justify-between font-semibold">
                  <span className="capitalize">{selectedTier}</span>
                  <span className="text-primary">{tierDetails[selectedTier].price}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{tierDetails[selectedTier].customers}</span>
                  <span>{tierDetails[selectedTier].routers}</span>
                </div>
              </div>
              {errors.subscription_tier && (
                <p className="text-sm text-destructive">{errors.subscription_tier.message}</p>
              )}
            </div>

            {errors.root && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {errors.root.message}
              </div>
            )}

            <Button
              type="submit"
              className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
              disabled={signupMutation.isPending}
            >
              {signupMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating account...
                </>
              ) : (
                'Create my account'
              )}
            </Button>
          </form>
        </CardContent>

        <CardFooter className="flex justify-center border-t p-4">
          <p className="text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary hover:underline">
              Sign in →
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}

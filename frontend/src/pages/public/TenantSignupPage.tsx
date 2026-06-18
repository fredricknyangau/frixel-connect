import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Eye, EyeOff, Loader2, Building2 } from 'lucide-react';
import { useRegisterTenant } from '../../hooks/useTenant';
import { PageTitle } from '../../components/shared/PageTitle';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';

const tierDetails = {
  starter: { price: 'KES 2,500/mo', limit: '100 Customers' },
  growth: { price: 'KES 5,000/mo', limit: '500 Customers' },
  scale: { price: 'KES 10,000/mo', limit: '2,000 Customers' },
  enterprise: { price: 'KES 25,000/mo', limit: '10,000+ Customers' },
};

const signupSchema = z
  .object({
    business_name: z.string().min(2, 'Business name must be at least 2 characters'),
    owner_email: z.string().email('Enter a valid email address'),
    owner_phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
    subscription_tier: z.enum(['starter', 'growth', 'scale', 'enterprise']),
  })
  .refine((data) => data.password === data.confirm, {
    message: "Passwords don't match",
    path: ['confirm'],
  });

type SignupFormValues = z.infer<typeof signupSchema>;

export default function TenantSignupPage() {
  const [searchParams] = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const registerTenant = useRegisterTenant();

  const urlTier = searchParams.get('tier') as SignupFormValues['subscription_tier'];
  const defaultTier = ['starter', 'growth', 'scale', 'enterprise'].includes(urlTier) ? urlTier : 'starter';

  const {
    register,
    handleSubmit,
    control,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      subscription_tier: defaultTier,
    },
  });

  const selectedTier = watch('subscription_tier') || 'starter';

  const onSubmit = async (data: SignupFormValues) => {
    try {
      await registerTenant.mutateAsync({
        business_name: data.business_name,
        owner_email: data.owner_email,
        owner_phone: data.owner_phone,
        password: data.password,
        subscription_tier: data.subscription_tier,
      });
    } catch (error: any) {
      if (error.response?.status === 409) {
        setError('owner_email', { message: 'This email is already registered.' });
      } else {
        setError('root', { message: error.response?.data?.detail || 'Registration failed. Please try again.' });
      }
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-140px)] items-center justify-center p-4 py-10">
      <PageTitle title="Start Your Free Trial | ZealSync" />
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mb-4 mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
            <Building2 className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Start Your Trial</CardTitle>
          <CardDescription>Launch your ISP billing operation instantly.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="business_name">Business/ISP Name</Label>
              <Input
                id="business_name"
                placeholder="e.g. Nairobi Net Services"
                {...register('business_name')}
              />
              {errors.business_name && <p className="text-sm text-destructive">{errors.business_name.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="owner_email">Owner Email</Label>
              <Input
                id="owner_email"
                type="email"
                placeholder="owner@example.com"
                {...register('owner_email')}
              />
              {errors.owner_email && <p className="text-sm text-destructive">{errors.owner_email.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="owner_phone">Owner M-Pesa Phone</Label>
              <Input
                id="owner_phone"
                type="tel"
                placeholder="e.g. 0712345678"
                {...register('owner_phone')}
              />
              {errors.owner_phone && <p className="text-sm text-destructive">{errors.owner_phone.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="subscription_tier">Subscription Tier</Label>
              <Controller
                control={control}
                name="subscription_tier"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="starter">Starter Trial (KES 2,500/mo)</SelectItem>
                      <SelectItem value="growth">Growth Trial (KES 5,000/mo)</SelectItem>
                      <SelectItem value="scale">Scale Trial (KES 10,000/mo)</SelectItem>
                      <SelectItem value="enterprise">Enterprise Trial (KES 25,000/mo)</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.subscription_tier && <p className="text-sm text-destructive">{errors.subscription_tier.message}</p>}
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
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm Password</Label>
              <div className="relative">
                <Input
                  id="confirm"
                  type={showConfirmPassword ? 'text' : 'password'}
                  {...register('confirm')}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirm && <p className="text-sm text-destructive">{errors.confirm.message}</p>}
            </div>

            {/* Selected Tier Pricing Info Box */}
            <div className="rounded-lg border bg-muted p-4 space-y-1 text-sm">
              <div className="flex justify-between font-semibold">
                <span className="capitalize">{selectedTier} Plan Trial</span>
                <span className="text-primary">{tierDetails[selectedTier].price}</span>
              </div>
              <div className="flex justify-between text-muted-foreground text-xs">
                <span>Maximum Capacity</span>
                <span>{tierDetails[selectedTier].limit}</span>
              </div>
            </div>

            {errors.root && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {errors.root.message}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting || registerTenant.isPending}>
              {isSubmitting || registerTenant.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating workspace...
                </>
              ) : (
                'Start 14-Day Free Trial'
              )}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center border-t p-4">
          <p className="text-sm text-muted-foreground">
            Already have an ISP workspace?{' '}
            <Link to="/login" className="text-primary hover:underline">
              Log in
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}

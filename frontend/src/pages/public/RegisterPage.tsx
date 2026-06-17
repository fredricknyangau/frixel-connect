import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useRegister } from '../../hooks/useAuth';
import { PageTitle } from '../../components/shared/PageTitle';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { UserRole } from '../../types/auth';

const registerSchema = z
  .object({
    email: z.string().email('Enter a valid email address'),
    phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
    role: z.enum(['admin', 'reseller', 'customer']),
  })
  .refine((data) => data.password === data.confirm, {
    message: "Passwords don't match",
    path: ['confirm'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const registerMutation = useRegister();

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      role: 'customer',
    },
  });

  const onSubmit = async (data: RegisterFormValues) => {
    try {
      await registerMutation.mutateAsync({
        email: data.email,
        phone: data.phone,
        password: data.password,
        role: data.role as UserRole,
      });
    } catch (error: any) {
      if (error.response?.status === 409) {
        // We set root error because the API might not specify if it's email or phone that conflicts
        // but showing it near the top is good enough, or we can map it to 'email' field explicitly
        setError('email', { message: 'This email or phone is already registered' });
      } else {
        setError('root', { message: 'An unexpected error occurred. Please try again.' });
      }
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-140px)] items-center justify-center p-4 py-10">
      <PageTitle title="Register" />
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mb-4 mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
            <span className="text-xl font-bold text-primary">Z</span>
          </div>
          <CardTitle className="text-2xl">Create an account</CardTitle>
          <CardDescription>Get started with ZealSync WiFi Billing.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="role">I am a...</Label>
              <Controller
                control={control}
                name="role"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="customer">WiFi Customer</SelectItem>
                      <SelectItem value="reseller">Reseller</SelectItem>
                      <SelectItem value="admin">ISP Owner</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.role && <p className="text-sm text-destructive">{errors.role.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                {...register('email')}
              />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="0712 345 678"
                {...register('phone')}
              />
              {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
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

            {errors.root && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {errors.root.message}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting || registerMutation.isPending}>
              {(isSubmitting || registerMutation.isPending) ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating account...
                </>
              ) : (
                'Register'
              )}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center border-t p-4">
          <p className="text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary hover:underline">
              Login
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
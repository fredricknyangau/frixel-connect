import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, User as UserIcon, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

import { useCustomerProfile, useUpdateCustomerProfile } from '../../hooks/useUsers';
import { PageTitle } from '../../components/shared/PageTitle';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';

const updateProfileSchema = z.object({
  email: z.string().email('Enter a valid email address').optional().or(z.literal('')),
  phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number').optional().or(z.literal('')),
  password: z.string().min(8, 'Password must be at least 8 characters').optional().or(z.literal('')),
});

type UpdateProfileFormValues = z.infer<typeof updateProfileSchema>;

export default function ProfilePage() {
  const navigate = useNavigate();
  const { data: profile, isLoading } = useCustomerProfile();
  const updateProfile = useUpdateCustomerProfile();

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<UpdateProfileFormValues>({
    resolver: zodResolver(updateProfileSchema),
  });

  useEffect(() => {
    if (profile) {
      reset({
        email: profile.email.endsWith('@guest.example.com') ? '' : profile.email,
        phone: profile.phone,
        password: '',
      });
    }
  }, [profile, reset]);

  const onSubmit = async (data: UpdateProfileFormValues) => {
    try {
      const payload: any = {};
      if (data.email) payload.email = data.email;
      if (data.phone) payload.phone = data.phone;
      if (data.password) payload.password = data.password;

      await updateProfile.mutateAsync(payload);
      toast.success('Profile updated successfully');
      
      // If they changed their email or password, clear the password field
      reset({ ...data, password: '' });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    }
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <PageTitle title="My Profile | Frixel Connect" />

      <div className="flex items-center gap-3">
        <div className="p-3 bg-primary/10 rounded-full text-primary">
          <UserIcon className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Account Settings</h2>
          <p className="text-muted-foreground">Update your personal information.</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Contact Information</CardTitle>
          <CardDescription>
            This phone number is used for M-Pesa payments and account recovery.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <form id="profile-form" onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email Address</Label>
                <Input 
                  id="email" 
                  type="email" 
                  placeholder={profile?.email.endsWith('@guest.example.com') ? 'Please provide a real email' : 'you@example.com'}
                  {...register('email')}
                />
                {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
                {profile?.email.endsWith('@guest.example.com') && (
                  <p className="text-xs text-amber-500">You are using a temporary guest email. Please update it.</p>
                )}
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
                <Label htmlFor="password">New Password (Leave blank to keep current)</Label>
                <Input 
                  id="password" 
                  type="password" 
                  placeholder="••••••••" 
                  {...register('password')} 
                />
                {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
              </div>
            </form>
          )}
        </CardContent>
        <CardFooter className="flex justify-end border-t p-4 bg-muted/30">
          <Button 
            type="submit" 
            form="profile-form" 
            disabled={isLoading || isSubmitting || updateProfile.isPending}
          >
            {isSubmitting || updateProfile.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-muted-foreground" />
            <CardTitle>Data & Privacy</CardTitle>
          </div>
          <CardDescription>
            Manage your personal data, download an archive, or delete your account.
          </CardDescription>
        </CardHeader>
        <CardFooter className="pt-2">
          <Button variant="outline" onClick={() => navigate('/customer/privacy')}>
            Manage Privacy Settings
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
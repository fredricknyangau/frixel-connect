import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Loader2, User as UserIcon } from 'lucide-react';
import { toast } from 'sonner';

import { useCustomerProfile, useUpdateCustomerProfile } from '../../hooks/useUsers';
import { PageTitle } from '../../components/shared/PageTitle';

import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../../components/ui/card';

const updateProfileSchema = z.object({
  phone: z.string().regex(/^(?:0|254|\+254)[17]\d{8}$/, 'Enter a valid Kenyan phone number'),
});

type UpdateProfileFormValues = z.infer<typeof updateProfileSchema>;

export default function ProfilePage() {
  const { data: profile, isLoading } = useCustomerProfile();
  const updateProfile = useUpdateCustomerProfile();

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<UpdateProfileFormValues>({
    resolver: zodResolver(updateProfileSchema),
  });

  useEffect(() => {
    if (profile) {
      reset({
        phone: profile.phone,
      });
    }
  }, [profile, reset]);

  const onSubmit = async (data: UpdateProfileFormValues) => {
    try {
      await updateProfile.mutateAsync(data);
      toast.success('Profile updated successfully');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    }
  };

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <PageTitle title="My Profile | ZealSync" />

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
                  value={profile?.email || ''} 
                  disabled 
                  className="bg-muted"
                />
                <p className="text-xs text-muted-foreground">Email address cannot be changed.</p>
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
    </div>
  );
}
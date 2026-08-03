import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Helmet } from 'react-helmet-async';
import { 
  UserPlus, 
  ShieldCheck, 
  Key, 
  Loader2, 
  X,
  Mail,
  User,
  Eye,
  EyeOff
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { superAdminApi } from '../../lib/superAdminApi';
import { useCreateSuperAdmin, useSuperAdmins } from '../../hooks/useSuperAdmin';
import { SuperAdminProfile } from '../../types/superAdmin';
import { LoadingSpinner } from '../../components/shared/LoadingSpinner';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';

// Zod validation for creating a new super admin
const createAccountSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  full_name: z.string().min(2, 'Full name must be at least 2 characters').max(100),
  password: z.string().min(12, 'Password must be at least 12 characters'),
});

type CreateAccountFormValues = z.infer<typeof createAccountSchema>;

export default function AccountsPage() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // Query all super admin accounts
  const { data: admins, isLoading: adminsLoading } = useSuperAdmins();

  // Query logged-in user profile
  const { data: me, isLoading: meLoading } = useQuery<SuperAdminProfile>({
    queryKey: ['super-admin', 'me'],
    queryFn: async () => {
      const response = await superAdminApi.get<SuperAdminProfile>('/super-admin/auth/me');
      return response.data;
    },
  });

  const createAdminMutation = useCreateSuperAdmin();

  // Hook Form setup
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateAccountFormValues>({
    resolver: zodResolver(createAccountSchema),
    defaultValues: {
      email: '',
      full_name: '',
      password: '',
    },
  });

  const onSubmit = (data: CreateAccountFormValues) => {
    createAdminMutation.mutate(data, {
      onSuccess: () => {
        toast.success(`Successfully created Super Admin: ${data.full_name}`);
        reset();
        setShowAddModal(false);
      },
      onError: (err: any) => {
        toast.error(err.response?.data?.detail || err.message || 'Failed to create Super Admin');
      },
    });
  };

  const formatDate = (isoStr: string | null) => {
    if (!isoStr) return 'Never';
    try {
      return new Date(isoStr).toLocaleDateString('en-KE', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
    } catch {
      return isoStr;
    }
  };

  const isLoading = adminsLoading || meLoading;

  if (isLoading) {
    return <LoadingSpinner size="lg" className="text-red-500" />;
  }

  const displayAdmins = admins || [];

  return (
    <div className="space-y-6">
      <Helmet>
        <title>⚠ SA | Accounts | Frixel Connect</title>
      </Helmet>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">Super Admins</h1>
          <p className="text-xs text-slate-400 mt-1">Manage administrative access keys and operator accounts.</p>
        </div>
        <Button
          onClick={() => setShowAddModal(true)}
          className="bg-red-650 hover:bg-red-600 text-white font-semibold text-xs h-9 flex items-center justify-center gap-1.5 self-start sm:self-auto"
        >
          <UserPlus className="h-4 w-4" />
          <span>Add Super Admin</span>
        </Button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/10">
        <table className="min-w-full divide-y divide-slate-800/80 text-left text-xs text-slate-350">
          <thead className="bg-slate-950/60 font-mono text-[10px] uppercase tracking-wider text-slate-550">
            <tr>
              <th className="px-4 py-3">Full Name</th>
              <th className="px-4 py-3">Email Address</th>
              <th className="px-4 py-3">Last Login</th>
              <th className="px-4 py-3">MFA Status</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 font-medium">
            {displayAdmins.map((admin) => (
              <tr key={admin.id} className="hover:bg-slate-900/20 transition-colors">
                <td className="px-4 py-3.5 text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-red-500" />
                  <span className="font-bold">{admin.full_name}</span>
                  {me && me.id === admin.id && (
                    <Badge variant="outline" className="text-[9px] bg-red-950/20 text-red-400 border-red-900/30 font-mono py-0 px-1 ml-1.5 uppercase font-bold">
                      You
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-3.5 text-slate-400">{admin.email}</td>
                <td className="px-4 py-3.5 text-slate-400 font-mono">{formatDate(admin.last_login_at)}</td>
                <td className="px-4 py-3.5">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                    admin.totp_verified_at
                      ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                      : "bg-amber-950/20 text-amber-400 border-amber-900/30"
                  }`}>
                    {admin.totp_verified_at ? 'Configured' : 'Pending setup'}
                  </span>
                </td>
                <td className="px-4 py-3.5">
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                    admin.is_active
                      ? "bg-emerald-950/20 text-emerald-400 border-emerald-900/30"
                      : "bg-slate-950/40 text-slate-400 border-slate-850"
                  }`}>
                    {admin.is_active ? 'Active' : 'Suspended'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ─── ADD SUPER ADMIN DIALOG ─────────────────────────────────────────── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-850 bg-slate-900 p-6 shadow-2xl space-y-4">
            
            {/* Header */}
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold tracking-tight text-slate-100 flex items-center gap-1.5">
                <UserPlus className="h-4.5 w-4.5 text-red-500" />
                <span>Create Operator Account</span>
              </h3>
              <button 
                onClick={() => {
                  setShowAddModal(false);
                  reset();
                }}
                className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              
              {/* Full Name */}
              <div className="space-y-1.5">
                <Label htmlFor="full_name" className="text-xs text-slate-300">Full Name</Label>
                <div className="relative">
                  <User className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
                  <Input
                    id="full_name"
                    placeholder="E.g. Fredrick Nyangau"
                    className="bg-slate-950/60 border-slate-850 text-slate-100 placeholder:text-slate-650 focus:border-red-500 pl-9 h-9 text-xs"
                    disabled={createAdminMutation.isPending}
                    {...register('full_name')}
                  />
                </div>
                {errors.full_name && (
                  <p className="text-[10px] font-medium text-red-400 mt-0.5">{errors.full_name.message}</p>
                )}
              </div>

              {/* Email */}
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs text-slate-300">Email Address</Label>
                <div className="relative">
                  <Mail className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="operator@Frixel Connect.com"
                    className="bg-slate-950/60 border-slate-850 text-slate-100 placeholder:text-slate-650 focus:border-red-500 pl-9 h-9 text-xs"
                    disabled={createAdminMutation.isPending}
                    {...register('email')}
                  />
                </div>
                {errors.email && (
                  <p className="text-[10px] font-medium text-red-400 mt-0.5">{errors.email.message}</p>
                )}
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs text-slate-300">Password (Min 12 Chars)</Label>
                <div className="relative">
                  <Key className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••••••"
                    className="bg-slate-950/60 border-slate-850 text-slate-100 placeholder:text-slate-650 focus:border-red-500 pl-9 pr-9 h-9 text-xs"
                    disabled={createAdminMutation.isPending}
                    {...register('password')}
                  />
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-[10px] font-medium text-red-400 mt-0.5">{errors.password.message}</p>
                )}
              </div>

              {/* Submission buttons */}
              <div className="flex justify-end gap-2 pt-2 border-t border-slate-850">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowAddModal(false);
                    reset();
                  }}
                  className="text-xs text-slate-400 hover:bg-slate-800"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createAdminMutation.isPending}
                  className="bg-red-655 hover:bg-red-600 text-white font-semibold text-xs h-8 flex items-center justify-center gap-1.5"
                >
                  {createAdminMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                  <span>Create Account</span>
                </Button>
              </div>

            </form>
          </div>
        </div>
      )}

    </div>
  );
}

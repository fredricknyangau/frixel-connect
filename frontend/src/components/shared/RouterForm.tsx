import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useState } from 'react';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Loader2, Eye, EyeOff } from 'lucide-react';

export const routerSchema = z.object({
  name: z.string().min(1, 'Router name is required'),
  host: z.string().min(1, 'Host/IP is required'),
  port: z.coerce.number().int().positive('Port must be positive'),
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required').optional().or(z.literal('')),
  site_name: z.string().min(1, 'Site/Location name is required'),
});

export type RouterFormValues = z.infer<typeof routerSchema>;

interface RouterFormProps {
  onSubmit: (data: RouterFormValues) => void | Promise<void>;
  defaultValues?: Partial<RouterFormValues>;
  isPending?: boolean;
  submitLabel?: string;
  onCancel?: () => void;
  isEdit?: boolean;
}

export function RouterForm({
  onSubmit,
  defaultValues,
  isPending,
  submitLabel = 'Add Router',
  onCancel,
  isEdit = false,
}: RouterFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [rotatePassword, setRotatePassword] = useState(!isEdit);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RouterFormValues>({
    resolver: zodResolver(
      isEdit && !rotatePassword
        ? routerSchema.extend({ password: z.string().optional() })
        : routerSchema
    ) as any,
    defaultValues: defaultValues || {
      name: '',
      host: '',
      port: 8728, // Default API port for MikroTik
      username: 'admin',
      password: '',
      site_name: '',
    },
  });

  const handleFormSubmit = (data: RouterFormValues) => {
    const payload = { ...data };
    if (isEdit && !rotatePassword) {
      delete payload.password;
    }
    return onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="router_name">Router Name</Label>
          <Input id="router_name" placeholder="e.g. Core Mikrotik" {...register('name')} />
          {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="site_name">Site/Location Name</Label>
          <Input id="site_name" placeholder="e.g. Nairobi CBD" {...register('site_name')} />
          {errors.site_name && <p className="text-sm text-destructive">{errors.site_name.message}</p>}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 space-y-2">
          <Label htmlFor="host">Host IP or Domain</Label>
          <Input id="host" placeholder="e.g. 192.168.88.1" {...register('host')} />
          {errors.host && <p className="text-sm text-destructive">{errors.host.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="port">API Port</Label>
          <Input id="port" type="number" {...register('port')} />
          {errors.port && <p className="text-sm text-destructive">{errors.port.message}</p>}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="username">Username</Label>
        <Input id="username" placeholder="e.g. admin" {...register('username')} />
        {errors.username && <p className="text-sm text-destructive">{errors.username.message}</p>}
      </div>

      {isEdit && (
        <div className="flex items-center space-x-2 py-2">
          <input
            id="rotate_password"
            type="checkbox"
            checked={rotatePassword}
            onChange={(e) => setRotatePassword(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
          />
          <Label htmlFor="rotate_password" className="text-sm font-medium leading-none cursor-pointer">
            Rotate credentials (change password)
          </Label>
        </div>
      )}

      {rotatePassword && (
        <div className="space-y-2">
          <Label htmlFor="router_password">Password</Label>
          <div className="relative">
            <Input
              id="router_password"
              type={showPassword ? 'text' : 'password'}
              placeholder={isEdit ? 'Enter new router password' : 'Router password'}
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
      )}

      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting || isPending}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting || isPending}>
          {(isSubmitting || isPending) ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            submitLabel
          )}
        </Button>
      </div>
    </form>
  );
}

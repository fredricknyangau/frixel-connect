import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Loader2 } from 'lucide-react';

export const packageSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().optional(),
  price_kes: z.coerce.number().positive('Price must be greater than 0'),
  duration_days: z.coerce.number().int().positive('Duration must be a positive number'),
  speed_mbps: z.coerce.number().int().positive('Speed must be a positive number'),
});

export type PackageFormValues = z.infer<typeof packageSchema>;

interface PackageFormProps {
  onSubmit: (data: PackageFormValues) => void | Promise<void>;
  defaultValues?: Partial<PackageFormValues>;
  isPending?: boolean;
  submitLabel?: string;
  onCancel?: () => void;
}

export function PackageForm({
  onSubmit,
  defaultValues,
  isPending,
  submitLabel = 'Save Package',
  onCancel,
}: PackageFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PackageFormValues>({
    resolver: zodResolver(packageSchema) as any,
    defaultValues: defaultValues || {
      name: '',
      description: '',
      price_kes: 0,
      duration_days: 0,
      speed_mbps: 0,
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Package Name</Label>
        <Input id="name" placeholder="e.g. Bronze Plan" {...register('name')} />
        {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="speed_mbps">Speed (Mbps)</Label>
          <Input id="speed_mbps" type="number" {...register('speed_mbps')} />
          {errors.speed_mbps && <p className="text-sm text-destructive">{errors.speed_mbps.message}</p>}
        </div>
        <div className="space-y-2">
          <Label htmlFor="duration_days">Duration (Days)</Label>
          <Input id="duration_days" type="number" {...register('duration_days')} />
          {errors.duration_days && <p className="text-sm text-destructive">{errors.duration_days.message}</p>}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="price_kes">Price (KES)</Label>
        <Input id="price_kes" type="number" {...register('price_kes')} />
        {errors.price_kes && <p className="text-sm text-destructive">{errors.price_kes.message}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description (Optional)</Label>
        <Input id="description" placeholder="Short description" {...register('description')} />
      </div>

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

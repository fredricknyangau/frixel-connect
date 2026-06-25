import { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Loader2 } from 'lucide-react';
import type { ServiceType } from '../../lib/onboarding';

const baseSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  description: z.string().optional(),
  price_kes: z.coerce.number().min(1, 'Price must be at least KES 1'),
  speed_mbps: z.coerce.number().min(1, 'Speed must be at least 1 Mbps'),
  duration_days: z.coerce.number().int().positive('Duration must be positive'),
});

export type PackageFormValues = z.infer<typeof baseSchema> & {
  duration_minutes: number;
};

export interface PackageFormSubmitValues {
  name: string;
  description: string;
  price_kes: number;
  speed_mbps: number;
  duration_minutes: number;
}

interface PackageFormProps {
  onSubmit: (data: PackageFormSubmitValues) => void | Promise<void>;
  defaultValues?: Partial<PackageFormSubmitValues>;
  isPending?: boolean;
  submitLabel?: string;
  onCancel?: () => void;
  /** When set, shows service-specific duration UI and read-only service badge */
  serviceType?: ServiceType;
  /** Hide service badge in admin CRUD mode */
  showServiceBadge?: boolean;
}

const HOTSPOT_DURATION_PRESETS = [
  { label: '1 day', days: 1 },
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: 'Custom', days: -1 },
] as const;

type PackageFormInput = z.input<typeof baseSchema>;
type PackageFormOutput = z.output<typeof baseSchema>;

export function PackageForm({
  onSubmit,
  defaultValues,
  isPending,
  submitLabel = 'Save Package',
  onCancel,
  serviceType,
  showServiceBadge = !!serviceType,
}: PackageFormProps) {
  const isPppoe = serviceType === 'pppoe';
  const [durationPreset, setDurationPreset] = useState<number>(isPppoe ? 30 : 1);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<PackageFormInput, unknown, PackageFormOutput>({
    resolver: zodResolver(baseSchema),
    defaultValues: {
      name: defaultValues?.name ?? '',
      description: defaultValues?.description ?? '',
      price_kes: defaultValues?.price_kes ?? undefined,
      speed_mbps: defaultValues?.speed_mbps ?? undefined,
      duration_days: isPppoe
        ? 30
        : defaultValues?.duration_minutes
          ? Math.round(defaultValues.duration_minutes / 1440)
          : 1,
    },
  });

  const durationDays = Number(watch('duration_days') ?? 1);

  useEffect(() => {
    if (isPppoe) {
      setValue('duration_days', 30);
      setDurationPreset(30);
    }
  }, [isPppoe, setValue]);

  const handleFormSubmit = (data: PackageFormOutput) => {
    onSubmit({
      name: data.name,
      description: data.description ?? '',
      price_kes: data.price_kes,
      speed_mbps: data.speed_mbps,
      duration_minutes: data.duration_days * 1440,
    });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
      {showServiceBadge && serviceType && (
        <div className="flex items-center gap-2">
          <Label className="text-muted-foreground">Service type</Label>
          <Badge variant={serviceType === 'hotspot' ? 'default' : 'secondary'}>
            {serviceType === 'hotspot' ? 'Hotspot' : 'Fiber PPPoE'}
          </Badge>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="name">Package name</Label>
        <Input
          id="name"
          placeholder={isPppoe ? 'e.g. Home Fiber 20Mbps' : 'e.g. Daily 10Mbps'}
          {...register('name')}
        />
        {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description (optional)</Label>
        <Input id="description" placeholder="Short description" {...register('description')} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="price_kes">Price (KES)</Label>
          <Input id="price_kes" type="number" min={1} {...register('price_kes')} />
          {errors.price_kes && (
            <p className="text-sm text-destructive">{errors.price_kes.message}</p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="speed_mbps">Speed (Mbps)</Label>
          <Input id="speed_mbps" type="number" min={1} {...register('speed_mbps')} />
          {errors.speed_mbps && (
            <p className="text-sm text-destructive">{errors.speed_mbps.message}</p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="duration_days">Duration</Label>
        {isPppoe ? (
          <>
            <Input id="duration_days" value="30 days (monthly)" readOnly disabled className="bg-muted" />
            <p className="text-xs text-muted-foreground">
              Fiber subscriptions bill monthly. Duration is fixed at 30 days.
            </p>
          </>
        ) : (
          <>
            <Select
              value={String(durationPreset)}
              onValueChange={(val) => {
                const days = Number(val);
                setDurationPreset(days);
                if (days > 0) {
                  setValue('duration_days', days);
                }
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select duration" />
              </SelectTrigger>
              <SelectContent>
                {HOTSPOT_DURATION_PRESETS.map((preset) => (
                  <SelectItem key={preset.label} value={String(preset.days)}>
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {durationPreset === -1 && (
              <Controller
                control={control}
                name="duration_days"
                render={({ field }) => (
                  <Input
                    type="number"
                    min={1}
                    placeholder="Custom days"
                    value={String(field.value ?? '')}
                    onChange={(e) => field.onChange(Number(e.target.value))}
                  />
                )}
              />
            )}
            {durationPreset !== -1 && (
              <p className="text-xs text-muted-foreground">
                {durationDays} day{durationDays !== 1 ? 's' : ''} session
              </p>
            )}
          </>
        )}
        {errors.duration_days && (
          <p className="text-sm text-destructive">{errors.duration_days.message}</p>
        )}
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

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Input } from '../../../../components/ui/input';
import { Label } from '../../../../components/ui/label';
import { Button } from '../../../../components/ui/button';
import { Wifi, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const schema = z.object({
  name: z.string().min(1, 'Router name is required').max(100),
  site_name: z.string().min(1, 'Site/location name is required').max(100),
  version: z.enum(['v7', 'v6']),
});

type FormValues = z.infer<typeof schema>;

interface RouterDetailsStepProps {
  onSuccess: (data: { router_id: string; version: 'v7' | 'v6'; details: any }) => void;
  isPending: boolean;
  onInit: (name: string, siteName: string) => Promise<any>;
}

export function RouterDetailsStep({ onSuccess, isPending, onInit }: RouterDetailsStepProps) {
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
      site_name: '',
      version: 'v7',
    },
  });

  const selectedVersion = watch('version');

  const onSubmit = async (values: FormValues) => {
    try {
      const response = await onInit(values.name, values.site_name);
      onSuccess({
        router_id: response.router_id,
        version: values.version,
        details: response,
      });
      toast.success('Router details initialized!');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to initialize router.');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Router Details</h3>
        <p className="text-sm text-muted-foreground">
          Enter a friendly name and the physical site location for this router.
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="name">Router Name</Label>
          <Input
            id="name"
            placeholder="e.g. Eastlands Site A"
            {...register('name')}
            className={errors.name ? 'border-destructive' : ''}
          />
          {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
        </div>

        <div className="space-y-2">
          <Label htmlFor="site_name">Site Name / Location</Label>
          <Input
            id="site_name"
            placeholder="e.g. Eastlands"
            {...register('site_name')}
            className={errors.site_name ? 'border-destructive' : ''}
          />
          {errors.site_name && <p className="text-xs text-destructive">{errors.site_name.message}</p>}
        </div>

        <div className="space-y-2">
          <Label>RouterOS Version</Label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setValue('version', 'v7')}
              className={`flex flex-col items-center justify-center rounded-lg border-2 p-4 text-center hover:bg-accent/50 focus:outline-none transition-all ${
                selectedVersion === 'v7'
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-muted bg-background text-muted-foreground'
              }`}
            >
              <span className="font-semibold text-sm">RouterOS v7 (Recommended)</span>
              <span className="text-xs opacity-80 mt-1">Supports native WireGuard REST API</span>
            </button>
            <button
              type="button"
              onClick={() => setValue('version', 'v6')}
              className={`flex flex-col items-center justify-center rounded-lg border-2 p-4 text-center hover:bg-accent/50 focus:outline-none transition-all ${
                selectedVersion === 'v6'
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-muted bg-background text-muted-foreground'
              }`}
            >
              <span className="font-semibold text-sm">RouterOS v6 (Legacy)</span>
              <span className="text-xs opacity-80 mt-1">Uses API socket (Port 8728)</span>
            </button>
          </div>
        </div>
      </div>

      <div className="pt-2">
        <Button type="submit" disabled={isPending} className="w-full flex items-center justify-center gap-2">
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Initializing...
            </>
          ) : (
            <>
              Initialize & Continue <Wifi className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

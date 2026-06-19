import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Input } from '../../../../components/ui/input';
import { Label } from '../../../../components/ui/label';
import { Button } from '../../../../components/ui/button';
import { Eye, EyeOff, Copy, Loader2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { ROUTEROS_COMMANDS } from '../RouterOSInstructions';

const schema = z.object({
  username: z.string().min(1, 'API username is required').max(100),
  password: z.string().min(4, 'API password must be at least 4 characters'),
  port: z.number().int().min(1).max(65535),
});

type FormValues = z.infer<typeof schema>;

interface APICredentialsStepProps {
  version: 'v7' | 'v6';
  onSuccess: () => void;
  isPending: boolean;
  onSave: (data: FormValues) => Promise<any>;
}

export function APICredentialsStep({
  version,
  onSuccess,
  isPending,
  onSave,
}: APICredentialsStepProps) {
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      username: 'zealsync-api',
      password: '',
      port: version === 'v7' ? 80 : 8728,
    },
  });

  const apiPassword = watch('password') || 'ChooseAStrongPassword';
  const apiPort = watch('port') || (version === 'v7' ? 80 : 8728);

  const commandUser = version === 'v7'
    ? ROUTEROS_COMMANDS.v7.create_api_user(apiPassword)
    : ROUTEROS_COMMANDS.v6.create_api_user(apiPassword);

  const commandService = version === 'v7'
    ? ROUTEROS_COMMANDS.v7.enable_rest_api(apiPort)
    : ROUTEROS_COMMANDS.v6.enable_router_api(apiPort);

  const combinedCommands = `${commandUser}\n\n${commandService}`;

  const onSubmit = async (values: FormValues) => {
    try {
      await onSave(values);
      toast.success('API credentials saved!');
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save credentials.');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Commands copied');
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Configure Router API</h3>
        <p className="text-sm text-muted-foreground">
          Create a secure, restricted API user and enable the appropriate RouterOS service.
        </p>
      </div>

      <div className="space-y-4">
        {/* Commands Card */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Run these CLI commands in Winbox Terminal:
            </span>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => copyToClipboard(combinedCommands)}
              className="h-7 text-xs gap-1 hover:bg-muted"
            >
              <Copy className="h-3 w-3" /> Copy All
            </Button>
          </div>
          <div className="relative">
            <pre className="p-3 bg-zinc-950 text-zinc-50 font-mono text-[11px] rounded border border-zinc-800 whitespace-pre-wrap select-all leading-relaxed max-h-[160px] overflow-y-auto">
              {combinedCommands}
            </pre>
          </div>
          <p className="text-[11px] text-muted-foreground italic leading-relaxed">
            {version === 'v7'
              ? 'Note: RouterOS v7 REST API runs on standard HTTP port 80. Ensure no other service blocks this port.'
              : 'Note: RouterOS v6 utilizes the binary RouterOS API on port 8728. The REST API is not supported on v6.'}
          </p>
        </div>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="username">API Username</Label>
            <Input
              id="username"
              placeholder="zealsync-api"
              {...register('username')}
              className={errors.username ? 'border-destructive' : ''}
            />
            {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">API Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Choose a strong password"
                {...register('password')}
                className={`pr-10 ${errors.password ? 'border-destructive' : ''}`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="port">API Port</Label>
            <Input
              id="port"
              type="number"
              placeholder={version === 'v7' ? '80' : '8728'}
              {...register('port', { valueAsNumber: true })}
              className={errors.port ? 'border-destructive' : ''}
            />
            {errors.port && <p className="text-xs text-destructive">{errors.port.message}</p>}
          </div>
        </div>
      </div>

      <div className="pt-2">
        <Button type="submit" disabled={isPending} className="w-full flex items-center justify-center gap-2">
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Saving...
            </>
          ) : (
            <>
              Save & Test API Connection <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

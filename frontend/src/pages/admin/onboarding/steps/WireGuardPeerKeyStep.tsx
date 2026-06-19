import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Input } from '../../../../components/ui/input';
import { Label } from '../../../../components/ui/label';
import { Button } from '../../../../components/ui/button';
import { Copy, Loader2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { ROUTEROS_COMMANDS, WINBOX_PATHS } from '../RouterOSInstructions';

const schema = z.object({
  peer_public_key: z
    .string()
    .length(44, 'WireGuard public keys must be exactly 44 characters')
    .regex(/^[a-zA-Z0-9+/]+={1}$/, 'Must be a valid base64 key ending with ='),
});

type FormValues = z.infer<typeof schema>;

interface WireGuardPeerKeyStepProps {
  version: 'v7' | 'v6';
  onSuccess: () => void;
  isPending: boolean;
  onRegister: (peerKey: string) => Promise<any>;
}

export function WireGuardPeerKeyStep({
  version,
  onSuccess,
  isPending,
  onRegister,
}: WireGuardPeerKeyStepProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      peer_public_key: '',
    },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await onRegister(values.peer_public_key);
      toast.success('MikroTik public key registered!');
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to register peer key.');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Command copied');
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Register MikroTik VPN Key</h3>
        <p className="text-sm text-muted-foreground">
          ZealSync needs your MikroTik's WireGuard public key to accept incoming connection handshakes.
        </p>
      </div>

      <div className="space-y-4">
        {version === 'v7' ? (
          <div className="space-y-4">
            {/* CLI Instruction */}
            <div className="space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                CLI Command to view Public Key:
              </span>
              <div className="relative">
                <pre className="p-3 bg-zinc-950 text-zinc-50 font-mono text-xs rounded border border-zinc-800 whitespace-pre-wrap select-all pr-12">
                  {ROUTEROS_COMMANDS.v7.get_public_key}
                </pre>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => copyToClipboard(ROUTEROS_COMMANDS.v7.get_public_key)}
                  className="absolute top-2 right-2 text-zinc-400 hover:text-zinc-50 hover:bg-zinc-800 h-8 w-8"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* GUI Instruction */}
            <div className="space-y-2 rounded-lg bg-muted/40 p-4 border border-muted text-sm">
              <span className="font-semibold block mb-1">Winbox GUI Path:</span>
              <p className="text-muted-foreground text-xs leading-relaxed">
                {WINBOX_PATHS.v7.get_public_key}
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-muted border border-border p-4 text-sm text-muted-foreground">
            WireGuard is not natively supported on RouterOS v6. If you've set up a custom VPN tunnel, enter your manual client public key or a placeholder key to continue.
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="peer_public_key">MikroTik WireGuard Public Key</Label>
          <Input
            id="peer_public_key"
            placeholder="e.g. abcdEFGH12345+67890ij/klmnopQRSTuvwxYZabcde="
            {...register('peer_public_key')}
            className={errors.peer_public_key ? 'border-destructive' : ''}
          />
          {errors.peer_public_key && (
            <p className="text-xs text-destructive">{errors.peer_public_key.message}</p>
          )}
        </div>
      </div>

      <div className="pt-2">
        <Button type="submit" disabled={isPending} className="w-full flex items-center justify-center gap-2">
          {isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" /> Registering...
            </>
          ) : (
            <>
              Register Key & Continue <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

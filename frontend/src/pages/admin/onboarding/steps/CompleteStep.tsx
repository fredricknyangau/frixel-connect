import { useEffect, useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { Check, ShieldCheck, Zap, RefreshCw, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface CompleteStepProps {
  routerId: string;
  name: string;
  siteName: string;
  vpnIp: string;
  onReset: () => void;
  onFinish: () => void;
  onComplete: () => Promise<any>;
}

export function CompleteStep({
  routerId,
  name,
  siteName,
  vpnIp,
  onReset,
  onFinish,
  onComplete,
}: CompleteStepProps) {
  const [isPending, setIsPending] = useState(true);

  useEffect(() => {
    const activateRouter = async () => {
      try {
        await onComplete();
        localStorage.removeItem('Frixel Connect_onboarding_router_id');
        localStorage.removeItem('Frixel Connect_onboarding_router_version');
        setIsPending(false);
        toast.success('MikroTik router is now online!');
      } catch (err: any) {
        setIsPending(false);
        toast.error(err.response?.data?.detail || 'Failed to finalize onboarding.');
      }
    };
    activateRouter();
  }, [routerId]);

  return (
    <div className="space-y-6 text-center">
      {isPending ? (
        <div className="flex flex-col items-center justify-center py-12 space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-primary"></div>
          <p className="text-sm text-muted-foreground">Activating router configuration...</p>
        </div>
      ) : (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
          {/* Animated Success Badge */}
          <div className="flex justify-center">
            <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-primary/10 border-2 border-primary text-primary shadow-lg shadow-primary/10">
              <Check className="h-10 w-10 animate-in fade-in zoom-in duration-300 delay-200" />
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-2xl font-bold text-foreground">Onboarding Complete!</h3>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              Your MikroTik router has been successfully registered and is now active for billing and provisioning.
            </p>
          </div>

          {/* Router Summary Box */}
          <div className="border rounded-xl bg-muted/20 text-left p-4 max-w-md mx-auto space-y-3.5">
            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block border-b pb-1">
              Router Details:
            </span>

            <div className="grid grid-cols-2 gap-y-3 text-xs leading-relaxed">
              <div>
                <span className="text-muted-foreground block">Router Name</span>
                <span className="font-semibold text-foreground">{name}</span>
              </div>
              <div>
                <span className="text-muted-foreground block">Site Location</span>
                <span className="font-semibold text-foreground">{siteName}</span>
              </div>
              <div>
                <span className="text-muted-foreground block">VPN Assigned IP</span>
                <span className="font-mono font-semibold text-foreground">{vpnIp}</span>
              </div>
              <div>
                <span className="text-muted-foreground block">API & Tunnel Connection</span>
                <span className="font-semibold text-primary flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary" /> Active
                </span>
              </div>
            </div>

            <div className="bg-background border rounded-lg p-3 flex items-start space-x-2 text-xs">
              <Zap className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
              <p className="text-muted-foreground leading-relaxed">
                <strong>Voucher Provisioning Ready:</strong> Customers purchasing WiFi packages at site{' '}
                <strong className="text-foreground">{siteName}</strong> will now have their voucher codes automatically provisioned onto this router.
              </p>
            </div>
          </div>

          {/* Optional Anti-Tethering Setup */}
          <div className="border rounded-xl bg-card text-left p-4 max-w-md mx-auto space-y-3 border-dashed border-primary/40">
            <span className="text-xs font-semibold text-primary uppercase tracking-wider block border-b pb-1">
              Optional: Prevent Hotspot Sharing
            </span>
            
            <p className="text-xs text-muted-foreground leading-relaxed">
              Want to block customers from sharing their active connection with other devices using mobile hotspots? Paste this command into your RouterOS Terminal:
            </p>

            <div className="relative font-mono">
              <pre className="p-3 pr-14 rounded-lg bg-zinc-950 text-zinc-50 text-[10px] overflow-x-auto whitespace-pre-wrap leading-relaxed border border-zinc-800">
                {`/ip firewall mangle add action=change-ttl chain=postrouting new-ttl=set:1 out-interface=bridge-local passthrough=yes`}
              </pre>
              <Button
                type="button"
                size="xs"
                variant="secondary"
                onClick={() => {
                  navigator.clipboard.writeText(`/ip firewall mangle add action=change-ttl chain=postrouting new-ttl=set:1 out-interface=bridge-local passthrough=yes`);
                  toast.success('Copied to clipboard');
                }}
                className="absolute top-2 right-2 text-[10px] h-6 px-2"
              >
                Copy
              </Button>
            </div>
            
            <p className="text-[10px] text-muted-foreground leading-normal italic">
              * Note: Replace "bridge-local" with your local bridge name if it differs on your device.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto pt-2">
            <Button variant="outline" onClick={onReset} className="flex-1 flex items-center justify-center gap-2">
              <RefreshCw className="h-4 w-4" /> Add Another Router
            </Button>
            <Button onClick={onFinish} className="flex-1 flex items-center justify-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground border-transparent">
              Go to Dashboard <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

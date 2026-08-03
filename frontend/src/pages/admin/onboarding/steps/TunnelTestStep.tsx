import { useEffect, useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { CheckCircle2, XCircle, Loader2, ChevronDown, ChevronUp, RefreshCw, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface TunnelTestStepProps {
  routerId: string;
  onSuccess: () => void;
  onTestTunnel: () => Promise<{ connected: boolean; latency_ms: number | null }>;
}

export function TunnelTestStep({ routerId, onSuccess, onTestTunnel }: TunnelTestStepProps) {
  const [status, setStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [latency, setLatency] = useState<number | null>(null);
  const [openAccordion, setOpenAccordion] = useState<number | null>(null);

  const runTest = async () => {
    setStatus('testing');
    try {
      const response = await onTestTunnel();
      if (response.connected) {
        setLatency(response.latency_ms);
        setStatus('success');
        toast.success('VPN tunnel connection successful!');
      } else {
        setStatus('failed');
        toast.error('VPN tunnel check failed. Router is unreachable.');
      }
    } catch (err: any) {
      setStatus('failed');
      toast.error(err.response?.data?.detail || 'Failed to check VPN tunnel.');
    }
  };

  useEffect(() => {
    runTest();
  }, [routerId]);

  const toggleAccordion = (index: number) => {
    setOpenAccordion(openAccordion === index ? null : index);
  };

  const troubleshootingItems = [
    {
      title: 'Did you add persistent-keepalive=25s to the peer config?',
      content: 'Without this option, your MikroTik only sends data when there is active user traffic. This keepalive forces it to maintain the NAT routing table mappings on intermediate firewalls so that Frixel Connect can communicate with it at any time.',
    },
    {
      title: 'Is the Frixel Connect public key entered correctly on your router?',
      content: 'Double-check the public key entered in Step 1. A single typo in the base64 key will cause WireGuard to reject packets silently without establishing a handshake.',
    },
    {
      title: 'Is your MikroTik connected to the internet?',
      content: 'Ensure your router has basic internet connectivity. Run "/ping 8.8.8.8" or check if other WAN traffic is flowing normally.',
    },
    {
      title: 'Check "last-handshake" on your MikroTik interface',
      content: 'Run "/interface wireguard peers print" in the terminal. The "last-handshake" column should show a time format (e.g. 10s or 1m45s) instead of being empty or showing "never". If it shows "never", no VPN packets have reached our server yet.',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Verify VPN Tunnel</h3>
        <p className="text-sm text-muted-foreground">
          We are checking if we can ping your router over the established WireGuard tunnel.
        </p>
      </div>

      <div className="flex flex-col items-center justify-center p-6 border rounded-lg bg-muted/20 min-h-[220px] transition-all">
        {status === 'testing' && (
          <div className="flex flex-col items-center space-y-4 text-center animate-pulse">
            <div className="relative flex h-16 w-16 items-center justify-center">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary/20 opacity-75"></span>
              <div className="relative rounded-full bg-primary/10 p-4 border border-primary/20">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-foreground text-sm">Testing VPN Tunnel...</p>
              <p className="text-xs text-muted-foreground max-w-sm">
                Frixel Connect is pinging your MikroTik's VPN address to confirm the tunnel is active. This usually takes 5-15 seconds.
              </p>
            </div>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col items-center space-y-4 text-center">
            <div className="rounded-full bg-primary/10 p-4 border border-primary/20 text-primary">
              <CheckCircle2 className="h-10 w-10" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-primary text-sm">VPN Tunnel Active!</p>
              <p className="text-xs text-muted-foreground">
                Successfully routed traffic to your MikroTik over VPN.
                {latency !== null && ` Latency: ${latency.toFixed(1)}ms.`}
              </p>
            </div>
          </div>
        )}

        {status === 'failed' && (
          <div className="flex flex-col items-center space-y-4 text-center w-full">
            <div className="rounded-full bg-destructive/10 p-4 border border-destructive/20 text-destructive">
              <XCircle className="h-10 w-10" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-destructive text-sm">Tunnel Connection Failed</p>
              <p className="text-xs text-muted-foreground">
                Could not reach your MikroTik over the VPN tunnel.
              </p>
            </div>

            {/* Troubleshooting accordions */}
            <div className="w-full text-left space-y-2 mt-4 max-w-md">
              <p className="text-xs font-semibold text-foreground mb-2">Troubleshooting Checklist:</p>
              {troubleshootingItems.map((item, idx) => (
                <div key={idx} className="border rounded-md bg-background overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleAccordion(idx)}
                    className="w-full flex items-center justify-between p-3 text-xs font-medium hover:bg-muted/50 text-foreground transition-all"
                  >
                    <span>{item.title}</span>
                    {openAccordion === idx ? <ChevronUp className="h-3 w-3 shrink-0" /> : <ChevronDown className="h-3 w-3 shrink-0" />}
                  </button>
                  {openAccordion === idx && (
                    <div className="p-3 border-t text-xs text-muted-foreground leading-relaxed bg-muted/10">
                      {item.content}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="flex gap-2 w-full max-w-md mt-4">
              <Button variant="outline" onClick={runTest} className="flex-1 flex items-center justify-center gap-2">
                <RefreshCw className="h-4 w-4" /> Test Again
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className="pt-2">
        <Button
          onClick={onSuccess}
          disabled={status !== 'success'}
          className="w-full flex items-center justify-center gap-2"
        >
          Next Step <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

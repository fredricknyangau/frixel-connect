import { useEffect, useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { CheckCircle2, XCircle, Loader2, ChevronDown, ChevronUp, RefreshCw, ArrowLeft, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface APITestStepProps {
  routerId: string;
  version: 'v7' | 'v6';
  onSuccess: () => void;
  onBack: () => void;
  onTestAPI: () => Promise<{ connected: boolean; profiles?: string[]; error?: string }>;
}

export function APITestStep({ routerId, version, onSuccess, onBack, onTestAPI }: APITestStepProps) {
  const [status, setStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [profiles, setProfiles] = useState<string[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [openAccordion, setOpenAccordion] = useState<number | null>(null);

  const runTest = async () => {
    setStatus('testing');
    setErrorMsg(null);
    try {
      const response = await onTestAPI();
      if (response.connected) {
        setProfiles(response.profiles || []);
        setStatus('success');
        toast.success('API connection verified successfully!');
      } else {
        setErrorMsg(response.error || 'Failed to authenticate.');
        setStatus('failed');
        toast.error('API connection failed.');
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'API connection timed out.');
      setStatus('failed');
      toast.error('API connection check failed.');
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
      title: `Is the ${version === 'v7' ? 'www (REST)' : 'api'} service enabled?`,
      content: `Run "/ip service print" in the terminal. The ${version === 'v7' ? 'www' : 'api'} service must be enabled (without an "X" flag) and configure the same port you saved in the previous step.`,
    },
    {
      title: 'Is the API user in the correct group?',
      content: `Run "/user print". Ensure the user "zealsync-api" exists and is assigned to "zealsync-api-group" with "${version === 'v7' ? 'api, read, write, test, rest-api' : 'api, read, write, test'}" policies enabled.`,
    },
    {
      title: `Is the firewall blocking port ${version === 'v7' ? '80' : '8728'} from 10.8.0.1?`,
      content: 'Run "/ip firewall filter print" and look for drop rules. If you have restrictive firewall rules, you must add an input rule allowing traffic from 10.8.0.1 (ZealSync server) to your API port.',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Verify API Connection</h3>
        <p className="text-sm text-muted-foreground">
          We are checking if ZealSync can log in and retrieve hotspot profile names from your router.
        </p>
      </div>

      <div className="flex flex-col items-center justify-center p-6 border rounded-lg bg-muted/20 min-h-[220px] transition-all">
        {status === 'testing' && (
          <div className="flex flex-col items-center space-y-4 text-center animate-pulse">
            <div className="rounded-full bg-primary/10 p-4 border border-primary/20">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-foreground text-sm">Connecting to your MikroTik API...</p>
              <p className="text-xs text-muted-foreground">
                Retrieving configuration profiles over the VPN tunnel.
              </p>
            </div>
          </div>
        )}

        {status === 'success' && (
          <div className="flex flex-col items-center space-y-4 text-center w-full">
            <div className="rounded-full bg-primary/10 p-4 border border-primary/20 text-primary">
              <CheckCircle2 className="h-10 w-10" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-primary text-sm">API Connection Successful!</p>
              <p className="text-xs text-muted-foreground">
                ZealSync has authenticated and connected to your MikroTik.
              </p>
            </div>
            {profiles.length > 0 ? (
              <div className="w-full text-left bg-background border rounded-md p-3 max-w-md">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase block mb-1">
                  Found {profiles.length} existing hotspot profiles:
                </span>
                <div className="flex flex-wrap gap-1.5 max-h-[80px] overflow-y-auto pt-1">
                  {profiles.map((p, i) => (
                    <span key={i} className="text-xs bg-muted px-2 py-0.5 rounded font-mono border">
                      {p}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic">No hotspot profiles found on this router.</p>
            )}
          </div>
        )}

        {status === 'failed' && (
          <div className="flex flex-col items-center space-y-4 text-center w-full">
            <div className="rounded-full bg-destructive/10 p-4 border border-destructive/20 text-destructive">
              <XCircle className="h-10 w-10" />
            </div>
            <div className="space-y-1 max-w-md">
              <p className="font-semibold text-destructive text-sm">API Connection Failed</p>
              {errorMsg && (
                <div className="bg-destructive/10 border border-destructive/20 text-destructive text-xs font-mono p-2 rounded break-all max-h-[100px] overflow-y-auto leading-relaxed">
                  {errorMsg}
                </div>
              )}
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

            <div className="flex flex-col sm:flex-row gap-2 w-full max-w-md mt-4">
              <Button variant="outline" onClick={onBack} className="flex-1 flex items-center justify-center gap-2">
                <ArrowLeft className="h-4 w-4" /> Back to Credentials
              </Button>
              <Button variant="secondary" onClick={runTest} className="flex-1 flex items-center justify-center gap-2">
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

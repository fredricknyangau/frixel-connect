import { useState } from 'react';
import { Button } from '../../../../components/ui/button';
import { Card, CardContent } from '../../../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../../components/ui/tabs';
import { Copy, Check, Terminal, FileText, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { ROUTEROS_COMMANDS, WINBOX_PATHS } from '../RouterOSInstructions';

interface WireGuardConfigStepProps {
  initDetails: {
    router_id: string;
    'Frixel Connect_server_endpoint': string;
    'Frixel Connect_public_key': string;
    assigned_ip: string;
    server_wg_ip: string;
  };
  version: 'v7' | 'v6';
  onNext: () => void;
}

export function WireGuardConfigStep({ initDetails, version, onNext }: WireGuardConfigStepProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = (text: string, fieldId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopiedField(null), 2000);
  };

  const params = {
    serverPublicKey: initDetails['Frixel Connect_public_key'],
    serverEndpoint: initDetails['Frixel Connect_server_endpoint'],
    assignedIp: initDetails.assigned_ip,
  };

  const cliCommands = version === 'v7' 
    ? ROUTEROS_COMMANDS.v7.wireguard_setup(params) 
    : ROUTEROS_COMMANDS.v6.wireguard_setup();

  const winboxInstructions = version === 'v7'
    ? WINBOX_PATHS.v7.wireguard
    : WINBOX_PATHS.v6.wireguard;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-foreground">Configure WireGuard on MikroTik</h3>
        <p className="text-sm text-muted-foreground">
          Use the details below to establish a secure VPN tunnel between Frixel Connect and your router.
        </p>
      </div>

      {/* Grid of parameters */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { label: 'Frixel Connect VPN Endpoint', value: initDetails['Frixel Connect_server_endpoint'], id: 'endpoint' },
          { label: 'Frixel Connect VPN Public Key', value: initDetails['Frixel Connect_public_key'], id: 'pubkey', truncate: true },
          { label: "Your Router's Assigned IP", value: `${initDetails.assigned_ip}/24`, id: 'assigned_ip' },
          { label: 'Frixel Connect VPN Server IP', value: initDetails.server_wg_ip, id: 'server_ip' },
        ].map((item) => (
          <Card key={item.id} className="bg-muted/30 border border-muted">
            <CardContent className="p-4 flex justify-between items-center space-x-2">
              <div className="space-y-1 overflow-hidden">
                <span className="text-xs text-muted-foreground font-medium block">{item.label}</span>
                <span className="text-sm font-mono truncate block text-foreground">
                  {item.value}
                </span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => copyToClipboard(item.value, item.id)}
                className="h-8 w-8 shrink-0 hover:bg-muted"
              >
                {copiedField === item.id ? <Check className="h-4 w-4 text-primary" /> : <Copy className="h-4 w-4" />}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Connection Mode Selection */}
      <Tabs defaultValue="cli" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="cli" className="flex items-center gap-2">
            <Terminal className="h-4 w-4" /> CLI Commands
          </TabsTrigger>
          <TabsTrigger value="gui" className="flex items-center gap-2">
            <FileText className="h-4 w-4" /> Winbox GUI Path
          </TabsTrigger>
        </TabsList>

        <TabsContent value="cli" className="mt-4">
          <div className="relative">
            <pre className="p-4 rounded-lg bg-zinc-950 text-zinc-50 font-mono text-xs overflow-x-auto whitespace-pre-wrap leading-relaxed border border-zinc-800 max-h-[300px]">
              {cliCommands}
            </pre>
            {version === 'v7' && (
              <Button
                size="xs"
                variant="secondary"
                onClick={() => copyToClipboard(cliCommands, 'cli')}
                className="absolute top-2 right-2 text-xs h-7 gap-1"
              >
                {copiedField === 'cli' ? <Check className="h-3 w-3 text-primary" /> : <Copy className="h-3 w-3" />}
                Copy All
              </Button>
            )}
          </div>
          {version === 'v7' && (
            <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
              <strong>Why <code className="font-mono text-foreground font-semibold">persistent-keepalive=25s</code>?</strong> This setting forces your MikroTik to send a heartbeat packet every 25 seconds. Since your router is on a private network, this keeps the firewall port open so Frixel Connect can initiate connections back to your router.
            </p>
          )}
        </TabsContent>

        <TabsContent value="gui" className="mt-4">
          <div className="p-4 rounded-lg bg-muted/40 border border-muted text-sm whitespace-pre-line leading-relaxed font-sans">
            {winboxInstructions}
          </div>
        </TabsContent>
      </Tabs>

      <div className="pt-2">
        <Button onClick={onNext} className="w-full flex items-center justify-center gap-2">
          I've configured this <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

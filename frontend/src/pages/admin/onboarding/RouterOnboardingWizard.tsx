import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { PageTitle } from '../../../components/shared/PageTitle';
import { Card, CardContent } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { CheckCircle2, ChevronRight, Wifi, ArrowLeft } from 'lucide-react';
import { api } from '../../../lib/api';
import { useRouterOnboarding } from '../../../hooks/useRouterOnboarding';

// Steps imports
import { RouterDetailsStep } from './steps/RouterDetailsStep';
import { WireGuardConfigStep } from './steps/WireGuardConfigStep';
import { WireGuardPeerKeyStep } from './steps/WireGuardPeerKeyStep';
import { TunnelTestStep } from './steps/TunnelTestStep';
import { APICredentialsStep } from './steps/APICredentialsStep';
import { APITestStep } from './steps/APITestStep';
import { ProfileSetupStep } from './steps/ProfileSetupStep';
import { CompleteStep } from './steps/CompleteStep';

const STEPS_LABELS = [
  'Details',
  'VPN Config',
  'Peer Key',
  'Tunnel Test',
  'Credentials',
  'API Test',
  'Profiles',
  'Complete',
];

export default function RouterOnboardingWizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const routerOnboarding = useRouterOnboarding();

  const [step, setStep] = useState<number>(0);
  const [routerId, setRouterId] = useState<string | null>(null);
  const [version, setVersion] = useState<'v7' | 'v6'>('v7');
  const [routerName, setRouterName] = useState<string>('');
  const [siteName, setSiteName] = useState<string>('');
  const [vpnIp, setVpnIp] = useState<string>('');

  const [initDetails, setInitDetails] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize mutations
  const initMutation = routerOnboarding.useInitOnboarding();
  const registerMutation = routerOnboarding.useRegisterPeer();
  const testTunnelMutation = routerOnboarding.useTestTunnel();
  const saveCredsMutation = routerOnboarding.useSaveCredentials();
  const testAPIMutation = routerOnboarding.useTestAPI();
  const setupProfilesMutation = routerOnboarding.useSetupProfiles();
  const completeMutation = routerOnboarding.useCompleteOnboarding();

  useEffect(() => {
    const checkResume = async () => {
      // 1. Check query param first, then localStorage
      const paramId = searchParams.get('router_id');
      const localId = localStorage.getItem('zealsync_onboarding_router_id');
      const activeId = paramId || localId;

      const localVersion = localStorage.getItem('zealsync_onboarding_router_version') as 'v7' | 'v6';
      if (localVersion) {
        setVersion(localVersion);
      }

      if (activeId) {
        try {
          setIsLoading(true);
          const response = await api.get(`/admin/routers/${activeId}`);
          const router = response.data;

          setRouterId(router.id);
          setRouterName(router.name);
          setSiteName(router.site_name);
          setVpnIp(router.wireguard_assigned_ip || '');

          if (router.port === 8728) {
            setVersion('v6');
          } else {
            setVersion('v7');
          }

          // Populate mock/cached init details
          setInitDetails({
            router_id: router.id,
            zealsync_server_endpoint: router.wireguard_public_key ? '[zealsync_server_ip]:51820' : 'Hetzner_Endpoint:51820', // Fallback or read from settings if returned
            zealsync_public_key: router.wireguard_public_key || '',
            assigned_ip: router.wireguard_assigned_ip || '',
            server_wg_ip: '10.8.0.1',
          });

          // Reconstruct initDetails with real server values if we hit the backend config
          // For simplicity, we fetch it during init or load it from backend
          // We can construct it:
          const initResp = await api.post('/admin/routers/onboarding/init', {
            name: router.name,
            site_name: router.site_name,
          }).catch(() => null);

          if (initResp) {
            setInitDetails(initResp.data);
          }

          // Determine resumed step
          if (router.status === 'pending_setup') {
            if (!router.wireguard_peer_public_key) {
              setStep(2); // Needs peer key
            } else {
              setStep(3); // Test tunnel
            }
          } else if (router.status === 'testing') {
            setStep(5); // Test API
          } else if (router.status === 'online') {
            setStep(7); // Complete
          } else {
            setStep(0);
          }
        } catch (err) {
          console.error('Failed to resume onboarding', err);
          localStorage.removeItem('zealsync_onboarding_router_id');
        } finally {
          setIsLoading(false);
        }
      } else {
        setIsLoading(false);
      }
    };

    checkResume();
  }, [searchParams]);

  const handleInitSuccess = (data: { router_id: string; version: 'v7' | 'v6'; details: any }) => {
    setRouterId(data.router_id);
    setVersion(data.version);
    setRouterName(data.details.name || '');
    setSiteName(data.details.site_name || '');
    setVpnIp(data.details.assigned_ip || '');
    setInitDetails(data.details);

    localStorage.setItem('zealsync_onboarding_router_id', data.router_id);
    localStorage.setItem('zealsync_onboarding_router_version', data.version);

    setStep(1);
  };

  const handleReset = () => {
    localStorage.removeItem('zealsync_onboarding_router_id');
    localStorage.removeItem('zealsync_onboarding_router_version');
    setRouterId(null);
    setInitDetails(null);
    setStep(0);
  };

  const handleBackToRouters = () => {
    navigate('/admin/routers');
  };

  return (
    <div className="flex flex-col min-h-screen bg-muted/30">
      <PageTitle title="MikroTik Router Setup Wizard | ZealSync" />

      {/* Header */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background px-6 shadow-sm">
        <div className="flex items-center space-x-3">
          <Button variant="ghost" size="icon" onClick={handleBackToRouters} className="h-8 w-8 text-muted-foreground">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center space-x-2">
            <Wifi className="h-5 w-5 text-primary" />
            <h1 className="text-base font-bold text-foreground tracking-tight">MikroTik Setup Wizard</h1>
          </div>
        </div>
        <div className="text-xs text-muted-foreground">
          {routerId ? (
            <span className="font-medium bg-muted px-2.5 py-1 rounded-full border">
              Router ID: <code className="font-mono text-foreground font-semibold">{routerId.substring(0, 8)}...</code>
            </span>
          ) : (
            <span className="italic">New Router Configuration</span>
          )}
        </div>
      </header>

      {/* Progress Stepper Bar */}
      <div className="bg-background border-b py-4 px-6 shadow-sm">
        {/* Desktop/Tablet view */}
        <div className="hidden md:flex items-center space-x-2 justify-between max-w-5xl mx-auto">
          {STEPS_LABELS.map((label, idx) => {
            const isActive = step === idx;
            const isCompleted = step > idx;

            return (
              <div key={idx} className="flex items-center space-x-2">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold border-2 transition-all ${
                    isActive
                      ? 'bg-primary border-primary text-primary-foreground scale-105 shadow-md shadow-primary/20'
                      : isCompleted
                      ? 'bg-primary/20 border-primary text-primary'
                      : 'bg-muted border-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : idx + 1}
                </div>
                <span
                  className={`text-xs font-medium ${
                    isActive ? 'text-foreground font-bold' : 'text-muted-foreground'
                  }`}
                >
                  {label}
                </span>
                {idx < STEPS_LABELS.length - 1 && <ChevronRight className="h-3.5 w-3.5 text-zinc-400" />}
              </div>
            );
          })}
        </div>

        {/* Mobile view */}
        <div className="flex md:hidden flex-col space-y-2 max-w-md mx-auto">
          <div className="flex justify-between items-center text-xs font-semibold">
            <span className="text-primary">Step {step + 1} of {STEPS_LABELS.length}</span>
            <span className="text-foreground">{STEPS_LABELS[step]}</span>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary transition-all duration-300 rounded-full" 
              style={{ width: `${((step + 1) / STEPS_LABELS.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-xl">
          {isLoading ? (
            <Card className="shadow-lg border">
              <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-primary"></div>
                <p className="text-sm text-muted-foreground">Retrieving onboarding setup context...</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="shadow-lg border bg-background border-t-4 border-t-primary rounded-xl overflow-hidden transition-all duration-300">
              <CardContent className="p-6 md:p-8">
                {step === 0 && (
                  <RouterDetailsStep
                    onInit={async (name, siteName) => {
                      return initMutation.mutateAsync({ name, site_name: siteName });
                    }}
                    isPending={initMutation.isPending}
                    onSuccess={handleInitSuccess}
                  />
                )}

                {step === 1 && initDetails && (
                  <WireGuardConfigStep
                    initDetails={initDetails}
                    version={version}
                    onNext={() => setStep(2)}
                  />
                )}

                {step === 2 && routerId && (
                  <WireGuardPeerKeyStep
                    version={version}
                    onRegister={async (peerKey) => {
                      return registerMutation.mutateAsync({ router_id: routerId, peer_public_key: peerKey });
                    }}
                    isPending={registerMutation.isPending}
                    onSuccess={() => setStep(3)}
                  />
                )}

                {step === 3 && routerId && (
                  <TunnelTestStep
                    routerId={routerId}
                    onTestTunnel={async () => {
                      return testTunnelMutation.mutateAsync({ router_id: routerId });
                    }}
                    onSuccess={() => setStep(4)}
                  />
                )}

                {step === 4 && routerId && (
                  <APICredentialsStep
                    version={version}
                    onSave={async (data) => {
                      return saveCredsMutation.mutateAsync({
                        router_id: routerId,
                        username: data.username,
                        password: data.password,
                        port: data.port,
                      });
                    }}
                    isPending={saveCredsMutation.isPending}
                    onSuccess={() => setStep(5)}
                  />
                )}

                {step === 5 && routerId && (
                  <APITestStep
                    routerId={routerId}
                    version={version}
                    onTestAPI={async () => {
                      return testAPIMutation.mutateAsync({ router_id: routerId });
                    }}
                    onBack={() => setStep(4)}
                    onSuccess={() => setStep(6)}
                  />
                )}

                {step === 6 && routerId && (
                  <ProfileSetupStep
                    onSetupProfiles={async (profiles) => {
                      return setupProfilesMutation.mutateAsync({ router_id: routerId, profiles });
                    }}
                    isPending={setupProfilesMutation.isPending}
                    onSuccess={() => setStep(7)}
                  />
                )}

                {step === 7 && routerId && (
                  <CompleteStep
                    routerId={routerId}
                    name={routerName}
                    siteName={siteName}
                    vpnIp={vpnIp}
                    onComplete={async () => {
                      return completeMutation.mutateAsync({ router_id: routerId });
                    }}
                    onReset={handleReset}
                    onFinish={handleBackToRouters}
                  />
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}

/**
 * src/pages/admin/onboarding/OnboardingWizard.tsx
 * =================================================
 * First-run onboarding wizard for new tenants.
 * 3 steps: Create package → Connect router → Done
 *
 * Step 2 update (Phase 5):
 *   Old: Embedded router form with manual WireGuard explanation
 *   New: Teaser card that navigates to the Magic Command wizard.
 *        When the user returns after completing the magic wizard,
 *        the useRouters() hook already polls for router data.
 *        The useEffect watches for any router with status='online'
 *        and auto-advances to Step 3.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageTitle } from '../../../components/shared/PageTitle';
import { PackageForm, PackageFormValues } from '../../../components/shared/PackageForm';
import { useCreatePackage } from '../../../hooks/usePackages';
import { useRouters } from '../../../hooks/useRouters';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { toast } from 'sonner';
import { CheckCircle2, Package, Wifi, ArrowRight, Zap } from 'lucide-react';

export default function OnboardingWizard() {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const createPackageMutation = useCreatePackage();

  // Poll for routers-when the magic wizard completes and the user navigates
  // back here, this data will already be fresh. The refetch interval is
  // handled by React Query's default staleTime.
  const { data: routers } = useRouters();

  // Auto-advance to Step 3 when any router is online.
  // This fires when the user returns from the router wizard OR when the
  // router calls /confirm while the user is still on this step.
  useEffect(() => {
    const hasOnlineRouter = routers?.some((r) => r.status === 'online');
    if (hasOnlineRouter && step === 2) {
      setStep(3);
    }
  }, [routers, step]);

  const handlePackageSubmit = async (data: PackageFormValues) => {
    try {
      await createPackageMutation.mutateAsync({
        ...data,
        duration_minutes: data.duration_minutes || 1440,
        description: data.description || '',
      });
      toast.success('First package created!');
      setStep(2);
    } catch {
      toast.error('Failed to create package. Please try again.');
    }
  };

  const handleFinish = () => {
    navigate('/admin/dashboard');
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <PageTitle title="ISP Setup Wizard | Frixel Connect" />
      <div className="w-full max-w-lg space-y-6">
        {/* Stepper Header */}
        <div className="flex items-center justify-between px-4">
          <div className="flex items-center space-x-2">
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-all ${step >= 1 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
              {step > 1 ? <CheckCircle2 className="h-4 w-4" /> : '1'}
            </div>
            <span className="text-xs sm:text-sm font-medium">Packages</span>
          </div>
          <div className="h-px flex-1 bg-muted-foreground/20 mx-2 sm:mx-4" />
          <div className="flex items-center space-x-2">
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-all ${step >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
              {step > 2 ? <CheckCircle2 className="h-4 w-4" /> : '2'}
            </div>
            <span className="text-xs sm:text-sm font-medium">Router</span>
          </div>
          <div className="h-px flex-1 bg-muted-foreground/20 mx-2 sm:mx-4" />
          <div className="flex items-center space-x-2">
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-all ${step >= 3 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}`}>
              3
            </div>
            <span className="text-xs sm:text-sm font-medium">Done</span>
          </div>
        </div>

        {/* Step 1: Create Package */}
        {step === 1 && (
          <Card className="border-t-4 border-t-primary">
            <CardHeader>
              <div className="flex items-center space-x-2 text-primary">
                <Package className="h-6 w-6" />
                <CardTitle className="text-xl">Create Your First Package</CardTitle>
              </div>
              <CardDescription>
                Define your WiFi plans and speed configurations. Customers can buy these packages on self-service portals.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <PackageForm
                onSubmit={handlePackageSubmit}
                submitLabel="Create Package & Continue"
                isPending={createPackageMutation.isPending}
              />
              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="text-sm text-muted-foreground hover:text-foreground hover:underline"
                >
                  I'll do this later
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Connect Router-Magic Command teaser */}
        {step === 2 && (
          <Card className="border-t-4 border-t-primary animate-in fade-in slide-in-from-bottom-4 duration-300">
            <CardHeader>
              <div className="flex items-center space-x-2 text-primary">
                <Wifi className="h-6 w-6" />
                <CardTitle className="text-xl">Connect Your First Router</CardTitle>
              </div>
              <CardDescription>
                Link Frixel Connect to your MikroTik router in about 60 seconds.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Magic Command teaser */}
              <div className="rounded-xl border bg-gradient-to-br from-primary/5 to-primary/10 p-5 space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15">
                    <Zap className="h-4 w-4 text-primary" />
                  </div>
                  <p className="font-semibold text-sm">One command does everything</p>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Frixel Connect generates a single terminal command. Paste it into your
                  MikroTik terminal, and the router configures itself-VPN, API user,
                  speed profiles, and firewall rules, all in one step.
                </p>
                <div className="rounded-lg bg-zinc-900 px-3.5 py-2.5 font-mono text-xs text-emerald-400 truncate">
                  /tool fetch url="https://api.Frixel Connect.dev/api/v1/setup/..." ...
                </div>
              </div>

              <Button
                onClick={() => navigate('/admin/onboarding/router')}
                className="w-full flex items-center justify-center gap-2 h-11"
                id="add-router-from-onboarding"
              >
                <Wifi className="h-4 w-4" />
                Add Router{' '}
                <ArrowRight className="h-4 w-4" />
              </Button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="text-sm text-muted-foreground hover:text-foreground hover:underline"
                >
                  I'll do this later
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Done */}
        {step === 3 && (
          <Card className="border-t-4 border-t-primary text-center p-6 animate-in fade-in scale-in duration-300">
            <CardHeader className="flex flex-col items-center">
              <div className="mb-2 h-14 w-14 bg-primary/10 text-primary rounded-full flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 animate-bounce" />
              </div>
              <CardTitle className="text-2xl">ISP Setup Complete!</CardTitle>
              <CardDescription>
                Your Frixel Connect workspace is ready to process automated payments and manage sessions.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                You can configure additional packages, routers, resellers, and customize portal layouts inside your main ISP Admin dashboard at any time.
              </p>
              <Button onClick={handleFinish} className="w-full flex items-center justify-center gap-2">
                Go to Dashboard <ArrowRight className="h-4 w-4" />
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

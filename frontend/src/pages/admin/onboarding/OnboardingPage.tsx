/**
 * Post-signup onboarding shell-guides new tenants through package creation,
 * router magic-command setup, and go-live confirmation before the admin dashboard.
 *
 * State persists in localStorage (zealsync_onboarding_state) so a browser refresh
 * resumes at the last incomplete step.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Wifi, CheckCircle2, AlertTriangle } from 'lucide-react';

import { PageTitle } from '../../../components/shared/PageTitle';
import { AnimatedCheckmark } from '../../../components/shared/AnimatedCheckmark';
import { PackageForm, PackageFormSubmitValues } from '../../../components/admin/PackageForm';
import RouterOnboardingWizard from './RouterOnboardingWizard';
import { useCreatePackage } from '../../../hooks/usePackages';
import { useTenantMe } from '../../../hooks/useTenant';
import { useAuthContext } from '../../../context/AuthContext';
import { Button } from '../../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import {
  readOnboardingState,
  writeOnboardingState,
  clearOnboardingState,
  getOnboardingServiceType,
  type OnboardingState,
  type OnboardingStep,
} from '../../../lib/onboarding';
import { cn } from '../../../lib/utils';

const STEPS: { key: OnboardingStep; number: number; title: string }[] = [
  { key: 'packages', number: 1, title: 'Create a package' },
  { key: 'router', number: 2, title: 'Connect your router' },
  { key: 'complete', number: 3, title: 'Go live' },
];

function stepIndex(step: OnboardingStep): number {
  return STEPS.findIndex((s) => s.key === step);
}

export default function OnboardingPage() {
  const navigate = useNavigate();
  const { logout } = useAuthContext();
  const { data: tenant } = useTenantMe();
  const createPackage = useCreatePackage();

  const [state, setState] = useState<OnboardingState>(() => {
    const existing = readOnboardingState();
    if (existing) return existing;
    const serviceType = getOnboardingServiceType();
    return {
      step: 'packages',
      packages_done: false,
      router_done: false,
      router_id: null,
      router_name: null,
      package_id: null,
      package_name: null,
      service_type: serviceType,
      started_at: new Date().toISOString(),
    };
  });

  useEffect(() => {
    writeOnboardingState(state);
  }, [state]);

  useEffect(() => {
    if (state.step === 'complete') {
      clearOnboardingState();
    }
  }, [state.step]);

  const currentIdx = stepIndex(state.step);

  const advanceTo = (step: OnboardingStep, patch: Partial<OnboardingState> = {}) => {
    setState((prev: OnboardingState) => ({ ...prev, ...patch, step }));
  };

  const handlePackageSubmit = async (data: PackageFormSubmitValues) => {
    try {
      const pkg = await createPackage.mutateAsync(data);
      toast.success('Package created!');
      advanceTo('router', {
        packages_done: true,
        package_id: pkg.id,
        package_name: pkg.name,
      });
    } catch {
      toast.error('Failed to create package. Please try again.');
    }
  };

  const handleSkipPackage = () => {
    advanceTo('router', { packages_done: false });
  };

  const handleRouterComplete = (routerId: string, routerName: string) => {
    advanceTo('complete', {
      router_done: true,
      router_id: routerId,
      router_name: routerName,
    });
  };

  const handleSkipRouter = () => {
    advanceTo('complete', { router_done: false });
  };

  const handleGoToDashboard = () => {
    navigate('/admin/dashboard');
  };

  const packageSubtitle =
    state.service_type === 'hotspot'
      ? 'Define what your customers buy-daily, weekly, or custom sessions with speed tiers.'
      : 'Define your monthly subscription plans-set the speed and price your customers pay each month.';

  const routerSubtitle =
    'Your router configures itself with one command. Takes about 60 seconds.';

  const skippedItems: string[] = [];
  if (!state.packages_done) skippedItems.push('packages');
  if (!state.router_done) skippedItems.push('router setup');

  return (
    <div className="flex min-h-screen flex-col bg-background dark">
      <PageTitle title="Setup Your ISP | ZealSync" />

      {/* Top bar-no sidebar during first-run onboarding */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-border/60 bg-background/95 px-4 backdrop-blur-sm md:px-6">
        <Link to="/" className="flex items-center gap-2">
          <Wifi className="h-5 w-5 text-primary" />
          <span className="font-bold text-primary">ZealSync</span>
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-muted-foreground sm:inline">{tenant?.owner_email}</span>
          <button
            type="button"
            onClick={logout}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 md:px-6">
        {/* Progress indicator */}
        <div className="mb-10">
          <div className="flex items-center justify-between">
            {STEPS.map((s, idx) => {
              const isActive = state.step === s.key;
              const isComplete = currentIdx > idx;
              return (
                <div key={s.key} className="flex flex-1 items-center">
                  <div className="flex flex-col items-center gap-2 min-w-0">
                    <div
                      className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-colors',
                        isComplete && 'bg-emerald-500 text-white',
                        isActive && !isComplete && 'bg-primary text-primary-foreground',
                        !isActive && !isComplete && 'bg-muted text-muted-foreground',
                      )}
                    >
                      {isComplete ? <CheckCircle2 className="h-5 w-5" /> : s.number}
                    </div>
                    <span
                      className={cn(
                        'text-center text-xs font-medium max-w-[90px] leading-tight',
                        isActive ? 'text-foreground' : 'text-muted-foreground',
                      )}
                    >
                      {s.title}
                    </span>
                  </div>
                  {idx < STEPS.length - 1 && (
                    <div
                      className={cn(
                        'mx-2 h-px flex-1',
                        currentIdx > idx ? 'bg-emerald-500' : 'bg-border',
                      )}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Step 1-Create first package */}
        {state.step === 'packages' && (
          <Card className="border-t-4 border-t-primary">
            <CardHeader>
              <CardTitle className="text-xl">Create your first package</CardTitle>
              <CardDescription>{packageSubtitle}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <PackageForm
                serviceType={state.service_type}
                onSubmit={handlePackageSubmit}
                submitLabel="Save package and continue"
                isPending={createPackage.isPending}
              />
              <div className="text-center">
                <button
                  type="button"
                  onClick={handleSkipPackage}
                  className="text-sm text-muted-foreground hover:text-foreground hover:underline"
                >
                  Skip for now
                </button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2-Connect router (embedded magic command wizard) */}
        {state.step === 'router' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold">Connect your MikroTik router</h2>
              <p className="mt-1 text-sm text-muted-foreground">{routerSubtitle}</p>
            </div>
            <RouterOnboardingWizard embedded onComplete={handleRouterComplete} />
            <div className="space-y-3 text-center">
              <button
                type="button"
                onClick={handleSkipRouter}
                className="text-sm text-muted-foreground hover:text-foreground hover:underline"
              >
                I&apos;ll connect my router later
              </button>
            </div>
          </div>
        )}

        {/* Step 3-Go live confirmation */}
        {state.step === 'complete' && (
          <Card className="border-t-4 border-t-primary">
            <CardContent className="space-y-6 p-6 sm:p-8">
              <div className="flex flex-col items-center text-center">
                <AnimatedCheckmark size={88} />
                <h2 className="mt-4 text-2xl font-bold">
                  You&apos;re ready to go, {tenant?.business_name ?? 'there'}!
                </h2>
              </div>

              <div className="rounded-xl border bg-muted/30 divide-y">
                <div className="flex items-center justify-between px-4 py-3 text-sm">
                  <span>Account created</span>
                  <span>✅</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3 text-sm">
                  <span>First package: {state.package_name ?? 'None yet'}</span>
                  <span>{state.packages_done ? '✅' : '⚠️'}</span>
                </div>
                <div className="flex items-center justify-between px-4 py-3 text-sm">
                  <span>Router connected: {state.router_name ?? 'None yet'}</span>
                  <span>{state.router_done ? '✅' : '⚠️'}</span>
                </div>
              </div>

              {skippedItems.length > 0 && (
                <div className="flex items-start gap-3 rounded-lg border border-amber-300/50 bg-amber-50/50 dark:bg-amber-950/20 px-4 py-3 text-sm">
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
                  <p className="text-muted-foreground">
                    You skipped {skippedItems.join(' and ')}. Visit{' '}
                    {!state.packages_done && (
                      <Link to="/admin/packages" className="text-primary hover:underline">
                        Packages
                      </Link>
                    )}
                    {!state.packages_done && !state.router_done && ' or '}
                    {!state.router_done && (
                      <Link to="/admin/routers" className="text-primary hover:underline">
                        Routers
                      </Link>
                    )}{' '}
                    from your dashboard to complete setup.
                  </p>
                </div>
              )}

              {!state.router_done && (
                <p className="text-center text-xs text-muted-foreground">
                  Without a router, ZealSync can&apos;t accept payments or create vouchers. You can
                  connect one anytime from the Routers section in your dashboard.
                </p>
              )}

              <Button
                onClick={handleGoToDashboard}
                className="h-12 w-full text-base font-semibold"
              >
                Go to my dashboard →
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

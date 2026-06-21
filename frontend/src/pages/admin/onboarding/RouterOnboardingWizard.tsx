/**
 * src/pages/admin/onboarding/RouterOnboardingWizard.tsx
 * ======================================================
 * Magic Command Router Onboarding Wizard
 *
 * Replaces the old 7-step manual WireGuard wizard with a 3-state flow:
 *   'details'  → Enter router name, site, and CHR mode toggle
 *   'command'  → Copy one command, paste into MikroTik terminal
 *   'complete' → Animated success screen with summary
 *
 * The wizard polls GET /admin/routers/onboarding/status/{id} every 3 seconds
 * while on the 'command' step. When the MikroTik router runs the downloaded
 * script and calls POST /setup/{token}/confirm, the status changes to 'online'
 * and the wizard automatically advances to 'complete'.
 *
 * CHR vs PHYSICAL MIKROTIK:
 *   The CHR toggle on the 'details' step switches is_chr=true/false.
 *   is_chr=true:  Script uses http://192.168.56.1:8000 (Ubuntu host-only IP)
 *                 Script omits WireGuard commands (same-machine networking)
 *   is_chr=false: Script uses https://api.zealsync.dev (production HTTPS)
 *                 Script includes full WireGuard setup
 *
 * RESUME LOGIC:
 *   If the admin navigates away and returns, the wizard checks for a
 *   ?resume=routerId query param or localStorage. If the router is still
 *   'pending_setup', it skips to the 'command' step and resumes polling.
 */

import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { PageTitle } from '../../../components/shared/PageTitle';
import { AnimatedCheckmark } from '../../../components/shared/AnimatedCheckmark';
import { Card, CardContent } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Label } from '../../../components/ui/label';
import { Input } from '../../../components/ui/input';
import { useInitMagic, useRouterStatus } from '../../../hooks/useRouterOnboarding';
import { formatNairobiDate } from '../../../lib/utils';
import { api } from '../../../lib/api';
import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  Check,
  Loader2,
  Wifi,
  Terminal,
  AlertCircle,
} from 'lucide-react';
import type { MagicInitResponse } from '../../../types/setup';

// ── Step type ─────────────────────────────────────────────────────────────────

type Step = 'details' | 'command' | 'complete';

// ── Main Component ─────────────────────────────────────────────────────────────

export default function RouterOnboardingWizard() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // ── Wizard state ─────────────────────────────────────────────────────────────
  const [step, setStep] = useState<Step>('details');

  // Form values (kept in state for display on the complete screen)
  const [routerName, setRouterName] = useState('');
  const [siteName, setSiteName] = useState('');
  const [isChr, setIsChr] = useState(false);

  // Magic command response from init-magic
  const [initData, setInitData] = useState<MagicInitResponse | null>(null);

  // Copy button state
  const [copied, setCopied] = useState(false);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Resume loading state
  const [isLoadingResume, setIsLoadingResume] = useState(true);

  // Form validation errors
  const [nameError, setNameError] = useState('');
  const [siteError, setSiteError] = useState('');

  // ── Hooks ─────────────────────────────────────────────────────────────────────
  const initMagic = useInitMagic();

  // Poll status every 3 seconds once we have a router_id and are on the command step
  const { data: statusData } = useRouterStatus(
    initData?.router_id ?? null,
    step === 'command',
  );

  // ── Resume logic ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const resumeId = searchParams.get('resume');
    const localId = localStorage.getItem('zealsync_magic_router_id');
    const localToken = localStorage.getItem('zealsync_magic_setup_token');
    const localIsChr = localStorage.getItem('zealsync_magic_is_chr') === 'true';
    const localCommand = localStorage.getItem('zealsync_magic_command');
    const localExpires = localStorage.getItem('zealsync_magic_expires_at');
    const localName = localStorage.getItem('zealsync_magic_router_name');
    const localSite = localStorage.getItem('zealsync_magic_site_name');

    const activeId = resumeId || localId;

    if (activeId && localToken && localCommand && localExpires) {
      // Check if the token has expired locally (rough check before API call)
      const expiresAt = new Date(localExpires);
      const now = new Date();

      if (expiresAt > now) {
        // Token still valid — check actual router status
        api.get(`/admin/routers/onboarding/status/${activeId}`)
          .then((response) => {
            const { status } = response.data;
            if (status === 'pending_setup') {
              // Restore wizard state and jump to command step
              setInitData({
                router_id: activeId,
                setup_token: localToken,
                magic_command: localCommand,
                expires_at: localExpires,
                is_chr: localIsChr,
              });
              setIsChr(localIsChr);
              setRouterName(localName || '');
              setSiteName(localSite || '');
              setStep('command');
            } else if (status === 'online') {
              // Already completed — go straight to success
              setInitData({
                router_id: activeId,
                setup_token: localToken,
                magic_command: localCommand,
                expires_at: localExpires,
                is_chr: localIsChr,
              });
              setRouterName(localName || '');
              setSiteName(localSite || '');
              setStep('complete');
              clearLocalStorage();
            }
            // If status is neither, fall through to details step
          })
          .catch(() => {
            // Router not found or other error — start fresh
            clearLocalStorage();
          })
          .finally(() => {
            setIsLoadingResume(false);
          });
      } else {
        // Token expired — show fresh form
        clearLocalStorage();
        setIsLoadingResume(false);
      }
    } else {
      setIsLoadingResume(false);
    }
  }, []); // Run once on mount

  // ── Auto-advance when router connects ─────────────────────────────────────────
  useEffect(() => {
    if (statusData?.status === 'online' && step === 'command') {
      // Brief flash of the green "Connected!" indicator before advancing.
      // The CSS transition in the status indicator already handles the visual.
      setTimeout(() => {
        setStep('complete');
        clearLocalStorage();
      }, 800);
    }
  }, [statusData?.status, step]);

  // ── Helpers ───────────────────────────────────────────────────────────────────

  function clearLocalStorage() {
    localStorage.removeItem('zealsync_magic_router_id');
    localStorage.removeItem('zealsync_magic_setup_token');
    localStorage.removeItem('zealsync_magic_command');
    localStorage.removeItem('zealsync_magic_expires_at');
    localStorage.removeItem('zealsync_magic_is_chr');
    localStorage.removeItem('zealsync_magic_router_name');
    localStorage.removeItem('zealsync_magic_site_name');
  }

  function saveLocalStorage(data: MagicInitResponse, name: string, site: string) {
    localStorage.setItem('zealsync_magic_router_id', data.router_id);
    localStorage.setItem('zealsync_magic_setup_token', data.setup_token);
    localStorage.setItem('zealsync_magic_command', data.magic_command);
    localStorage.setItem('zealsync_magic_expires_at', data.expires_at);
    localStorage.setItem('zealsync_magic_is_chr', String(data.is_chr));
    localStorage.setItem('zealsync_magic_router_name', name);
    localStorage.setItem('zealsync_magic_site_name', site);
  }

  async function handleCopyCommand() {
    if (!initData) return;
    try {
      await navigator.clipboard.writeText(initData.magic_command);
      setCopied(true);
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available (non-HTTPS or browser restriction)
      toast.error('Could not copy automatically. Please select and copy the command manually.');
    }
  }

  async function handleSubmitDetails(e: React.FormEvent) {
    e.preventDefault();

    // Validate
    let valid = true;
    if (!routerName.trim()) {
      setNameError('Router name is required');
      valid = false;
    } else {
      setNameError('');
    }
    if (!siteName.trim()) {
      setSiteError('Site name is required');
      valid = false;
    } else {
      setSiteError('');
    }
    if (!valid) return;

    try {
      const data = await initMagic.mutateAsync({
        name: routerName.trim(),
        site_name: siteName.trim(),
        is_chr: isChr,
      });
      setInitData(data);
      saveLocalStorage(data, routerName.trim(), siteName.trim());
      setStep('command');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      const detail = axiosErr?.response?.data?.detail;
      toast.error(detail || 'Failed to generate setup command. Please try again.');
    }
  }

  function handleReset() {
    clearLocalStorage();
    setInitData(null);
    setRouterName('');
    setSiteName('');
    setIsChr(false);
    setNameError('');
    setSiteError('');
    setCopied(false);
    setStep('details');
  }

  // ── Render: Loading ───────────────────────────────────────────────────────────

  if (isLoadingResume) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30">
        <PageTitle title="Router Setup | ZealSync" />
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Checking setup status...</p>
        </div>
      </div>
    );
  }

  // ── Render: Full Page Wrapper ─────────────────────────────────────────────────

  return (
    <div className="flex flex-col min-h-screen bg-muted/30">
      <PageTitle title="Connect a Router | ZealSync" />

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-background/95 backdrop-blur-sm px-6 shadow-sm">
        <div className="flex items-center space-x-3">
          {step === 'command' && (
            <button
              onClick={() => setStep('details')}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Back to details"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Back</span>
            </button>
          )}
          <div className="flex items-center space-x-2">
            <Wifi className="h-5 w-5 text-primary" />
            <h1 className="text-base font-bold tracking-tight">Connect a Router</h1>
          </div>
        </div>

        {/* Progress indicator (only shown during 2-step flow) */}
        {(step === 'command') && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary font-semibold text-[10px]">✓</span>
              <span className="hidden sm:inline text-primary font-medium">Details</span>
            </div>
            <div className="h-px w-6 bg-muted-foreground/30" />
            <div className="flex items-center gap-1.5">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground font-semibold text-[10px]">2</span>
              <span className="hidden sm:inline font-medium">Run Command</span>
            </div>
          </div>
        )}
      </header>

      {/* ── Main Content ───────────────────────────────────────────────────── */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md">

          {/* ════════════════════════════════════════════════
              STEP: details
              ════════════════════════════════════════════════ */}
          {step === 'details' && (
            <Card className="border shadow-xl bg-background rounded-2xl overflow-hidden border-t-4 border-t-primary">
              <CardContent className="p-6 sm:p-8">
                {/* Header */}
                <div className="mb-6">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10">
                      <Terminal className="h-4.5 w-4.5 text-primary" />
                    </div>
                    <h2 className="text-xl font-bold tracking-tight">Connect a Router</h2>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Takes about 60 seconds. One command does everything.
                  </p>
                </div>

                <form onSubmit={handleSubmitDetails} className="space-y-5" noValidate>
                  {/* Router name */}
                  <div className="space-y-1.5">
                    <Label htmlFor="router-name" className="text-sm font-medium">
                      Router Name
                    </Label>
                    <Input
                      id="router-name"
                      type="text"
                      placeholder="Eastlands Site A"
                      value={routerName}
                      onChange={(e) => {
                        setRouterName(e.target.value);
                        if (nameError) setNameError('');
                      }}
                      className={nameError ? 'border-destructive focus-visible:ring-destructive' : ''}
                      autoFocus
                      autoComplete="off"
                    />
                    {nameError && (
                      <p className="text-xs text-destructive flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {nameError}
                      </p>
                    )}
                  </div>

                  {/* Site name */}
                  <div className="space-y-1.5">
                    <Label htmlFor="site-name" className="text-sm font-medium">
                      Site Name
                    </Label>
                    <Input
                      id="site-name"
                      type="text"
                      placeholder="Eastlands"
                      value={siteName}
                      onChange={(e) => {
                        setSiteName(e.target.value);
                        if (siteError) setSiteError('');
                      }}
                      className={siteError ? 'border-destructive focus-visible:ring-destructive' : ''}
                      autoComplete="off"
                    />
                    {siteError && (
                      <p className="text-xs text-destructive flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {siteError}
                      </p>
                    )}
                  </div>

                  {/* CHR mode toggle — native checkbox styled as a toggle */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-3">
                      <div>
                        <Label
                          htmlFor="chr-mode"
                          className="text-sm font-medium cursor-pointer"
                        >
                          Testing with CHR (VirtualBox)
                        </Label>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Uses your local IP instead of the cloud API
                        </p>
                      </div>
                      {/* Pill-style toggle — pure CSS, no shadcn dependency */}
                      <button
                        id="chr-mode"
                        type="button"
                        role="switch"
                        aria-checked={isChr}
                        onClick={() => setIsChr((v) => !v)}
                        className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                          isChr ? 'bg-primary' : 'bg-muted-foreground/30'
                        }`}
                      >
                        <span
                          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                            isChr ? 'translate-x-5' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>

                    {/* CHR warning banner */}
                    {isChr && (
                      <div className="flex items-start gap-2.5 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 px-3.5 py-3 text-sm">
                        <span className="text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0">⚠</span>
                        <div className="text-amber-800 dark:text-amber-300">
                          <span className="font-semibold">CHR mode active — </span>
                          commands use your local IP (192.168.56.1). WireGuard
                          is skipped since CHR and the backend share the same machine.{' '}
                          <span className="font-medium">Disable this for a physical MikroTik.</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Submit */}
                  <Button
                    type="submit"
                    className="w-full h-11 text-base font-semibold"
                    disabled={initMagic.isPending}
                    id="generate-setup-command"
                  >
                    {initMagic.isPending ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Generating command...
                      </>
                    ) : (
                      'Generate Setup Command'
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}

          {/* ════════════════════════════════════════════════
              STEP: command
              ════════════════════════════════════════════════ */}
          {step === 'command' && initData && (
            <div className="space-y-4">

              {/* Main command card */}
              <Card className="border shadow-xl bg-background rounded-2xl overflow-hidden border-t-4 border-t-primary">
                <CardContent className="p-6 sm:p-8 space-y-5">
                  {/* Title */}
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">
                      Run this on your MikroTik
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Open your MikroTik terminal and paste this command:
                    </p>
                  </div>

                  {/* Command block */}
                  <div className="rounded-xl bg-zinc-950 dark:bg-zinc-900 border border-zinc-800 overflow-hidden">
                    {/* Command bar */}
                    <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-zinc-800/60">
                      <span className="h-2.5 w-2.5 rounded-full bg-zinc-600" />
                      <span className="h-2.5 w-2.5 rounded-full bg-zinc-600" />
                      <span className="h-2.5 w-2.5 rounded-full bg-zinc-600" />
                      <span className="ml-2 text-xs text-zinc-500 font-mono">MikroTik Terminal</span>
                    </div>
                    {/* Command text */}
                    <div className="p-4">
                      <code
                        className="text-sm font-mono text-emerald-400 leading-relaxed break-all select-all"
                        id="magic-command-text"
                      >
                        {initData.magic_command}
                      </code>
                    </div>
                  </div>

                  {/* Copy button */}
                  <Button
                    onClick={handleCopyCommand}
                    className="w-full h-11 text-base font-semibold"
                    variant={copied ? 'default' : 'default'}
                    id="copy-magic-command"
                  >
                    {copied ? (
                      <>
                        <Check className="mr-2 h-4 w-4" />
                        Copied! ✓
                      </>
                    ) : (
                      <>
                        <Copy className="mr-2 h-4 w-4" />
                        Copy Command
                      </>
                    )}
                  </Button>

                  {/* Instructions */}
                  <div className="rounded-xl border bg-muted/30 p-4 space-y-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                      How to run it
                    </p>
                    <ol className="space-y-2.5">
                      {[
                        {
                          num: 1,
                          title: 'Open your MikroTik terminal',
                          desc: 'SSH, Winbox → New Terminal, or WebFig → Terminal',
                        },
                        {
                          num: 2,
                          title: 'Paste the command and press Enter',
                          desc: 'The router will download and run the setup script',
                        },
                        {
                          num: 3,
                          title: 'Wait about 30 seconds',
                          desc: 'This page updates automatically when done',
                        },
                      ].map((item) => (
                        <li key={item.num} className="flex items-start gap-3">
                          <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary text-[11px] font-bold mt-0.5">
                            {item.num}
                          </span>
                          <div>
                            <p className="text-sm font-medium leading-tight">{item.title}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>

                  {/* Live status indicator */}
                  <div className="flex items-center gap-3 px-1">
                    {statusData?.status === 'online' ? (
                      <>
                        {/* Green connected dot */}
                        <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
                        </span>
                        <p className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
                          Router connected! Setting up...
                        </p>
                      </>
                    ) : (
                      <>
                        {/* Grey pulse waiting dot */}
                        <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-muted-foreground/40 opacity-60" />
                          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-muted-foreground/50" />
                        </span>
                        <p className="text-sm text-muted-foreground">
                          Waiting for your router to connect...
                        </p>
                      </>
                    )}
                  </div>

                  {/* Expiry notice */}
                  <p className="text-xs text-muted-foreground text-center pt-1">
                    This command expires{' '}
                    <span className="font-medium">
                      {formatNairobiDate(initData.expires_at)}
                    </span>
                  </p>
                </CardContent>
              </Card>

              {/* CHR mode reminder */}
              {initData.is_chr && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 px-4 py-3 text-xs text-amber-800 dark:text-amber-300">
                  <span className="text-amber-600 dark:text-amber-400 flex-shrink-0">⚠</span>
                  <span>
                    <span className="font-semibold">CHR mode — </span>
                    command uses <code className="font-mono bg-amber-100 dark:bg-amber-900/50 px-1 rounded">192.168.56.1</code>.
                    Make sure CHR can reach your Ubuntu host.
                  </span>
                </div>
              )}
            </div>
          )}

          {/* ════════════════════════════════════════════════
              STEP: complete
              ════════════════════════════════════════════════ */}
          {step === 'complete' && initData && (
            <Card className="border shadow-xl bg-background rounded-2xl overflow-hidden">
              <CardContent className="p-6 sm:p-8">

                {/* Animated checkmark */}
                <div className="flex flex-col items-center text-center mb-6 pt-2">
                  <AnimatedCheckmark size={88} />
                  <h2 className="text-2xl font-bold tracking-tight mt-4">
                    Router Connected!
                  </h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    Your MikroTik is now linked to ZealSync and ready to process sessions.
                  </p>
                </div>

                {/* Summary card */}
                <div className="rounded-xl border bg-muted/30 divide-y divide-border mb-6 overflow-hidden">
                  {[
                    { label: 'Router name', value: routerName || 'Router' },
                    { label: 'Site', value: siteName || 'Site' },
                    {
                      label: 'Status',
                      value: (
                        <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 font-medium">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Online
                        </span>
                      ),
                    },
                    {
                      label: 'Network',
                      value: initData.is_chr
                        ? 'Local (VirtualBox host-only)'
                        : 'WireGuard VPN (10.8.x.x)',
                    },
                    {
                      label: 'API user',
                      value: (
                        <span className="flex items-center gap-1.5">
                          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                            zealsync-api
                          </code>
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        </span>
                      ),
                    },
                    {
                      label: 'Speed tiers',
                      value: (
                        <span className="flex items-center gap-1.5">
                          <span className="text-xs">10 / 20 / 50 Mbps</span>
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                        </span>
                      ),
                    },
                  ].map((row) => (
                    <div
                      key={row.label}
                      className="flex items-center justify-between px-4 py-3"
                    >
                      <span className="text-sm text-muted-foreground">{row.label}</span>
                      <span className="text-sm font-medium">{row.value}</span>
                    </div>
                  ))}
                </div>

                {/* Action buttons */}
                <div className="space-y-2.5">
                  <Button
                    onClick={handleReset}
                    variant="outline"
                    className="w-full h-10"
                    id="add-another-router"
                  >
                    <Wifi className="mr-2 h-4 w-4" />
                    Add Another Router
                  </Button>
                  <Button
                    onClick={() => navigate('/admin/dashboard')}
                    className="w-full h-10"
                    id="go-to-dashboard"
                  >
                    Go to Dashboard
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}

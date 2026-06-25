import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link } from 'react-router-dom';
import { Eye, EyeOff, Shield, Check, Loader2, ArrowLeft } from 'lucide-react';
import { useSuperAdminAuth } from '../../context/SuperAdminAuthContext';
import {
  usePasswordLogin,
  useTOTPSetup,
  useTOTPVerify,
} from '../../hooks/useSuperAdminAuth';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';

// Zod validation for Step 1
const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function SuperAdminLoginPage() {
  const { loginStep, setLoginStep, preAuthToken, setPreAuthToken } = useSuperAdminAuth();

  // Mutations
  const passwordLoginMutation = usePasswordLogin();
  const totpSetupMutation = useTOTPSetup();
  const totpVerifyMutation = useTOTPVerify();

  // Local component states
  const [showPassword, setShowPassword] = useState(false);
  const [totpCode, setTotpCode] = useState('');
  const [shake, setShake] = useState(false);
  const [showSuccessCheck, setShowSuccessCheck] = useState(false);
  const [hadSetup, setHadSetup] = useState(false);
  const [qrCodeData, setQrCodeData] = useState<{ qr_code_base64: string; secret_preview: string } | null>(null);

  const totpInputRef = useRef<HTMLInputElement>(null);

  // React Hook Form for Step 1
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  // If we land on the TOTP setup step, fetch setup details
  useEffect(() => {
    if (loginStep === 'totp_setup' && preAuthToken) {
      setHadSetup(true);
      totpSetupMutation.mutate(
        { pre_auth_token: preAuthToken },
        {
          onSuccess: (data) => {
            setQrCodeData(data);
          },
        }
      );
    }
  }, [loginStep, preAuthToken]);

  // Focus TOTP input when verification screen displays
  useEffect(() => {
    if (loginStep === 'totp_verify' && totpInputRef.current) {
      totpInputRef.current.focus();
    }
  }, [loginStep]);

  // Handle Step 1 Submit
  const onPasswordSubmit = (data: LoginFormValues) => {
    passwordLoginMutation.mutate(data);
  };

  // Handle auto-submit of TOTP code
  const handleTotpChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.replace(/[^0-9]/g, '').slice(0, 6);
    setTotpCode(val);

    if (val.length === 6 && preAuthToken) {
      totpVerifyMutation.mutate(
        { pre_auth_token: preAuthToken, totp_code: val },
        {
          onSuccess: () => {
            setShowSuccessCheck(true);
          },
          onError: () => {
            setShake(true);
            setTotpCode('');
            setTimeout(() => setShake(false), 500);
            if (totpInputRef.current) {
              totpInputRef.current.focus();
            }
          },
        }
      );
    }
  };

  // Reset auth flow
  const handleResetAuth = () => {
    setPreAuthToken(null);
    setLoginStep('idle');
    setTotpCode('');
    setQrCodeData(null);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 text-slate-100">
      <style>{`
        @keyframes shrink {
          from { width: 100%; }
          to { width: 0%; }
        }
        .animate-totp-timer {
          animation: shrink 30s linear infinite;
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%, 60% { transform: translateX(-6px); }
          40%, 80% { transform: translateX(6px); }
        }
        .animate-shake {
          animation: shake 0.4s ease-in-out;
        }
      `}</style>

      {/* Screen Card */}
      <div className="w-full max-w-xs space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-2xl backdrop-blur-md">
        
        {/* Header Branding */}
        <div className="flex flex-col items-center text-center">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
            <Shield className="h-5 w-5" />
          </div>
          <Badge variant="outline" className="font-mono text-[10px] tracking-widest text-teal-400 border-teal-800 bg-teal-950/30 uppercase px-2 py-0.5 mb-1.5">
            ZealSync Admin
          </Badge>
        </div>

        {/* SCREEN 1-'password' / 'idle' */}
        {(loginStep === 'idle' || loginStep === 'password') && (
          <div className="space-y-4">
            <div className="text-center">
              <h2 className="text-xl font-bold tracking-tight text-slate-100">Sign In</h2>
              <p className="text-xs text-slate-400 mt-1">Credentials verification gateway</p>
            </div>

            <form onSubmit={handleSubmit(onPasswordSubmit)} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs text-slate-300">Administrative Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="fredrick@zealsync.com"
                  className="bg-slate-950/60 border-slate-800 text-slate-100 placeholder:text-slate-600 focus:border-teal-500 h-9"
                  disabled={passwordLoginMutation.isPending}
                  {...register('email')}
                />
                {errors.email && (
                  <p className="text-[10px] font-medium text-red-400 mt-0.5">{errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs text-slate-300">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    placeholder="••••••••••••"
                    className="bg-slate-950/60 border-slate-800 text-slate-100 placeholder:text-slate-600 focus:border-teal-500 pr-9 h-9"
                    disabled={passwordLoginMutation.isPending}
                    {...register('password')}
                  />
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-[10px] font-medium text-red-400 mt-0.5">{errors.password.message}</p>
                )}
              </div>

              {passwordLoginMutation.isError && (
                <div className="rounded-lg bg-red-950/30 border border-red-900/30 p-2 text-center text-xs text-red-400">
                  {passwordLoginMutation.error?.response?.data?.detail || 'Authentication failed'}
                </div>
              )}

              <Button
                type="submit"
                className="w-full bg-teal-600 text-white hover:bg-teal-500 shadow-md shadow-teal-900/10 font-semibold h-9 mt-2 flex items-center justify-center gap-1.5"
                disabled={passwordLoginMutation.isPending}
              >
                {passwordLoginMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <span>Sign In</span>
                )}
              </Button>
            </form>

            <div className="text-center pt-2">
              <Link
                to="/login"
                className="text-[11px] text-slate-500 hover:text-teal-400 transition-colors"
              >
                Back to ISP portal
              </Link>
            </div>
          </div>
        )}

        {/* SCREEN 2-'totp_setup' */}
        {loginStep === 'totp_setup' && (
          <div className="space-y-4 text-center">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-slate-100">Set up authenticator</h2>
              <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                Scan this QR code with Google Authenticator, Authy, or any TOTP app. You'll need this app every time you log in. If you lose access, database-level recovery is required.
              </p>
            </div>

            {totpSetupMutation.isPending ? (
              <div className="flex h-[200px] w-full items-center justify-center rounded-xl bg-slate-950/60 border border-slate-800">
                <Loader2 className="h-8 w-8 animate-spin text-teal-400" />
              </div>
            ) : qrCodeData ? (
              <div className="flex flex-col items-center space-y-3">
                <div className="overflow-hidden rounded-xl border-4 border-slate-950 bg-white p-1 shadow-inner">
                  <img
                    src={qrCodeData.qr_code_base64}
                    alt="TOTP QR code"
                    className="h-[180px] w-[180px] object-contain"
                  />
                </div>
                <div className="text-[10px] text-slate-400 bg-slate-950/60 border border-slate-800/80 px-2.5 py-1.5 rounded-lg w-full font-mono break-all leading-normal">
                  Can't scan? Enter code manually:
                  <div className="font-semibold text-teal-400 mt-0.5 uppercase tracking-wider">
                    {qrCodeData.secret_preview}...
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-lg bg-red-950/30 border border-red-900/30 p-3 text-xs text-red-400">
                Failed to load setup details. Please restart the login process.
              </div>
            )}

            <div className="space-y-2 pt-2">
              <Button
                type="button"
                onClick={() => setLoginStep('totp_verify')}
                className="w-full bg-teal-600 text-white hover:bg-teal-500 font-semibold h-9 flex items-center justify-center gap-1.5"
                disabled={totpSetupMutation.isPending || !qrCodeData}
              >
                <span>I've scanned it</span>
                <ArrowLeft className="h-4 w-4 rotate-180" />
              </Button>
              
              <button
                onClick={handleResetAuth}
                className="text-[11px] text-slate-500 hover:text-slate-300 block w-full transition-colors pt-1"
              >
                Cancel setup
              </button>
            </div>
          </div>
        )}

        {/* SCREEN 3-'totp_verify' */}
        {loginStep === 'totp_verify' && (
          <div className="space-y-5 text-center">
            <div>
              <h2 className="text-lg font-bold tracking-tight text-slate-100">Enter security code</h2>
              <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed px-1">
                {hadSetup
                  ? 'Enter the code from your authenticator app to confirm setup.'
                  : 'Open your authenticator app and enter the current code.'}
              </p>
            </div>

            {/* Success Checkmark Anim */}
            {showSuccessCheck ? (
              <div className="flex h-20 w-full items-center justify-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-500 text-white shadow-lg shadow-teal-500/20">
                  <Check className="h-6 w-6 stroke-[3px]" />
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className={shake ? 'animate-shake' : ''}>
                  <input
                    ref={totpInputRef}
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    value={totpCode}
                    onChange={handleTotpChange}
                    disabled={totpVerifyMutation.isPending}
                    placeholder="000 000"
                    className="w-full text-center tracking-[0.75em] pl-[0.75em] text-2xl font-bold bg-slate-950/60 border border-slate-800 rounded-xl h-12 focus:border-teal-500 outline-none transition-colors text-slate-100 disabled:opacity-50"
                  />
                </div>

                {totpVerifyMutation.isError && (
                  <p className="text-[10px] font-medium text-red-400">
                    {totpVerifyMutation.error?.response?.data?.detail || 'Invalid verification code'}
                  </p>
                )}

                {/* Subtle Countdown Indicator */}
                <div className="space-y-1.5 pt-1">
                  <div className="w-full h-1 bg-slate-950/60 border border-slate-800/80 rounded-full overflow-hidden">
                    <div className="h-full bg-teal-500 animate-totp-timer" />
                  </div>
                  <p className="text-[9px] text-slate-500 tracking-wider">CODE REFRESH WINDOW</p>
                </div>
              </div>
            )}

            <div className="pt-2">
              <button
                onClick={handleResetAuth}
                disabled={totpVerifyMutation.isPending}
                className="text-[11px] text-slate-500 hover:text-teal-400 transition-colors flex items-center justify-center gap-1 mx-auto disabled:opacity-50"
              >
                <ArrowLeft className="h-3 w-3" />
                <span>Use a different account</span>
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from 'react'
import { useHotspotPaymentStatus } from '../../hooks/useHotspotPayment'
import { Loader2, CheckCircle2, XCircle, RefreshCw, CreditCard } from 'lucide-react'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'

interface Props {
  paymentId: string
  onConfirmed: (voucherCode: string) => void
  packagePrice: number
  packageName: string
}

export default function PaymentPolling({ paymentId, onConfirmed, packagePrice, packageName }: Props) {
  const startTime = useRef(Date.now())
  const TIMEOUT_SECONDS = 90
  const [timeLeft, setTimeLeft] = useState(TIMEOUT_SECONDS)

  const timedOut = timeLeft === 0

  const { data, refetch, isFetching } = useHotspotPaymentStatus(paymentId, !timedOut)

  useEffect(() => {
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime.current) / 1000)
      const remaining = Math.max(0, TIMEOUT_SECONDS - elapsed)
      setTimeLeft(remaining)
      if (remaining <= 0) {
        clearInterval(timer)
      }
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (data?.status === 'confirmed' && data?.voucher_code) {
      // Small delay so the user sees the success state before redirect
      setTimeout(() => onConfirmed(data.voucher_code!), 1500)
    }
  }, [data, onConfirmed])

  if (data?.status === 'confirmed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center bg-muted/50">
        <div className="bg-card p-8 rounded-xl shadow-lg border max-w-sm flex flex-col items-center">
          <CheckCircle2 className="text-primary w-16 h-16 mb-4 animate-bounce" />
          <h2 className="text-2xl font-bold text-foreground">Payment Confirmed!</h2>
          <p className="text-muted-foreground mt-2 text-sm">Activating your internet connection...</p>
        </div>
      </div>
    )
  }

  if (data?.status === 'failed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center bg-muted/50">
        <div className="bg-card p-8 rounded-xl shadow-lg border max-w-sm flex flex-col items-center">
          <XCircle className="text-destructive w-16 h-16 mb-4 animate-pulse" />
          <h2 className="text-2xl font-bold text-foreground">Payment Failed</h2>
          <p className="text-muted-foreground mt-2 text-sm">Please make sure you entered the correct PIN or have enough balance.</p>
          <Button className="mt-6 w-full" onClick={() => window.location.reload()}>
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  if (timedOut) {
    const paybillAccount = `WIFI-${paymentId.slice(0, 7).toUpperCase()}`
    const paybillNumber = import.meta.env.VITE_MPESA_PAYBILL || '174379'
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center bg-muted/50">
        <div className="bg-card p-6 rounded-xl shadow-lg border max-w-sm flex flex-col items-center space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-bold text-foreground">This is taking longer than usual</h2>
            <p className="text-muted-foreground text-xs leading-normal">
              Your M-Pesa prompt may still be processing. You can check again manually below.
            </p>
          </div>

          <div className="w-full flex flex-col gap-2.5">
            <Button onClick={() => refetch()} disabled={isFetching} className="w-full">
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              {isFetching ? 'Verifying...' : 'Verify Status'}
            </Button>
            <Button variant="outline" onClick={() => window.location.reload()} className="w-full">
              Back to Packages
            </Button>
          </div>

          {/* Manual Paybill instructions */}
          <Card className="w-full bg-muted/40 border border-dashed text-left p-3.5">
            <CardContent className="p-0 space-y-3">
              <div className="flex items-center gap-1.5 text-primary text-xs font-semibold">
                <CreditCard className="h-4 w-4" />
                <span>Pay Manually via Lipa na M-Pesa</span>
              </div>
              <div className="bg-card p-3 rounded-lg space-y-2 font-mono text-[10px] border">
                <div className="flex justify-between border-b pb-1.5">
                  <span className="text-muted-foreground">1. Paybill No</span>
                  <span className="font-bold text-foreground">{paybillNumber}</span>
                </div>
                <div className="flex justify-between border-b pb-1.5">
                  <span className="text-muted-foreground">2. Account No</span>
                  <span className="font-bold text-primary">{paybillAccount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">3. Amount</span>
                  <span className="font-bold text-foreground">KES {packagePrice}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  const progressPercent = (timeLeft / TIMEOUT_SECONDS) * 100
  const paybillAccount = `WIFI-${paymentId.slice(0, 7).toUpperCase()}`
  const paybillNumber = import.meta.env.VITE_MPESA_PAYBILL || '174379'

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center bg-muted/50">
      <div className="bg-card p-6 rounded-xl shadow-lg border w-full max-w-sm flex flex-col items-center">
        <Loader2 className="animate-spin text-primary w-12 h-12 mb-4" />
        <h2 className="text-xl font-bold text-foreground">Waiting for M-Pesa PIN</h2>
        <p className="text-muted-foreground text-xs mt-2 mb-6 leading-relaxed">
          Please check your phone, enter your M-Pesa PIN for <b>{packageName}</b>, and wait for confirmation.
        </p>

        {/* Progress Bar / Countdown */}
        <div className="w-full bg-muted rounded-full h-2 mb-2.5 overflow-hidden">
          <div 
            className="bg-primary h-full transition-all duration-1000 ease-linear rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <p className="text-[10px] text-muted-foreground mb-6">
          Request timing out in <b>{timeLeft}s</b>
        </p>

        {/* Verify Status button */}
        <Button 
          variant="outline" 
          onClick={() => refetch()} 
          disabled={isFetching}
          className="w-full mb-4 text-xs h-10"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
          {isFetching ? 'Checking status...' : 'Verify Status'}
        </Button>

        {/* Fallback instructions shown after 15 seconds */}
        {timeLeft <= 75 && (
          <Card className="w-full border-dashed border-primary/30 text-left p-3.5 bg-primary/5 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <CardContent className="p-0 space-y-3">
              <div className="flex items-center gap-1.5 text-primary text-xs font-semibold">
                <CreditCard className="h-4 w-4" />
                <span>Prompt delayed? Pay manually:</span>
              </div>
              <div className="bg-card p-3 rounded-lg space-y-2 font-mono text-[10px] border">
                <div className="flex justify-between border-b pb-1.5">
                  <span className="text-muted-foreground">1. Paybill No</span>
                  <span className="font-bold text-foreground">{paybillNumber}</span>
                </div>
                <div className="flex justify-between border-b pb-1.5">
                  <span className="text-muted-foreground">2. Account No</span>
                  <span className="font-bold text-primary">{paybillAccount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">3. Amount</span>
                  <span className="font-bold text-foreground">KES {packagePrice}</span>
                </div>
              </div>
              <p className="text-[9px] text-muted-foreground leading-normal italic">
                * M-Pesa will auto-confirm within seconds of entering your PIN.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

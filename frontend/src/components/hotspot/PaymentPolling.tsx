import { useEffect, useRef } from 'react'
import { useHotspotPaymentStatus } from '../../hooks/useHotspotPayment'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '../ui/button'

interface Props {
  paymentId: string
  onConfirmed: (voucherCode: string) => void
}

export default function PaymentPolling({ paymentId, onConfirmed }: Props) {
  const startTime = useRef(Date.now())
  const TIMEOUT_MS = 90_000

  const timedOut = Date.now() - startTime.current > TIMEOUT_MS

  const { data } = useHotspotPaymentStatus(paymentId, !timedOut)

  useEffect(() => {
    if (data?.status === 'confirmed' && data?.voucher_code) {
      // Small delay so the user sees the success state before redirect
      setTimeout(() => onConfirmed(data.voucher_code!), 1500)
    }
  }, [data, onConfirmed])

  if (data?.status === 'confirmed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center">
        <CheckCircle2 className="text-primary w-16 h-16 mb-4" />
        <h2 className="text-2xl font-bold text-foreground">Payment confirmed!</h2>
        <p className="text-muted-foreground mt-2">Connecting you now...</p>
      </div>
    )
  }

  if (data?.status === 'failed') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center">
        <XCircle className="text-destructive w-16 h-16 mb-4" />
        <h2 className="text-2xl font-bold text-foreground">Payment failed</h2>
        <p className="text-muted-foreground mt-2">Please try again.</p>
        <Button className="mt-6" onClick={() => window.location.reload()}>
          Try Again
        </Button>
      </div>
    )
  }

  if (timedOut) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center">
        <p className="text-foreground font-medium">This is taking longer than usual.</p>
        <p className="text-muted-foreground text-sm mt-2">
          Your payment may still be processing. Check your SMS for a voucher code,
          or wait a moment and refresh this page.
        </p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center">
      <Loader2 className="animate-spin text-primary w-12 h-12 mb-4" />
      <h2 className="text-xl font-bold text-foreground">
        Waiting for M-Pesa confirmation
      </h2>
      <p className="text-muted-foreground text-sm mt-2">
        Check your phone and enter your M-Pesa PIN
      </p>
    </div>
  )
}

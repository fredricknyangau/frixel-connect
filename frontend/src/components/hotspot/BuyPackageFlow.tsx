import { useState } from 'react'
import { useHotspotPackages } from '../../hooks/useHotspotPackages'
import { useHotspotSTKPush } from '../../hooks/useHotspotPayment'
import { formatKES } from '../../lib/utils'
import { formatDuration } from '../../lib/formatDuration'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Card, CardContent } from '../ui/card'
import { Badge } from '../ui/badge'
import { Loader2, Zap } from 'lucide-react'
import PaymentPolling from './PaymentPolling'

interface Props {
  tenantId: string
  macAddress: string
  clientIp: string
  onVoucherReceived: (code: string) => void
}

export default function BuyPackageFlow({ tenantId, macAddress, clientIp, onVoucherReceived }: Props) {
  const { data: packages, isLoading } = useHotspotPackages(tenantId)
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null)
  const [phone, setPhone] = useState('')
  const [paymentId, setPaymentId] = useState<string | null>(null)
  const [phoneError, setPhoneError] = useState('')

  const selectedPackage = packages?.find(p => p.id === selectedPackageId)

  const stkMutation = useHotspotSTKPush()

  const validatePhone = (value: string) => {
    const kenyanPhone = /^(?:0|254|\+254)[17]\d{8}$/
    if (!kenyanPhone.test(value)) {
      setPhoneError('Enter a valid Kenyan phone number (e.g. 0712 345 678)')
      return false
    }
    setPhoneError('')
    return true
  }

  const handlePay = () => {
    if (!selectedPackageId) return
    if (!validatePhone(phone)) return
    
    stkMutation.mutate({
      phone,
      package_id: selectedPackageId,
      tenant_id: tenantId,
      mac_address: macAddress,
      client_ip: clientIp,
    }, {
      onSuccess: (data) => {
        setPaymentId(data.id)
      }
    })
  }

  // Once STK push is initiated, show the polling screen
  if (paymentId) {
    return (
      <PaymentPolling
        paymentId={paymentId}
        onConfirmed={onVoucherReceived}
      />
    )
  }

  return (
    <div className="min-h-screen bg-muted/50 flex flex-col items-center justify-start p-4 pt-8">
      <p className="text-muted-foreground mb-6 text-center text-sm">
        Select a plan and pay with M-Pesa to get online instantly
      </p>

      {/* Package cards */}
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="animate-spin text-primary w-8 h-8" />
        </div>
      ) : (
        <div className="w-full max-w-sm space-y-3 mb-6">
          {packages?.map(pkg => (
            <Card
              key={pkg.id}
              className={`cursor-pointer transition-all border-2 ${
                selectedPackageId === pkg.id
                  ? 'border-primary bg-primary/10'
                  : 'border-border bg-card'
              }`}
              onClick={() => setSelectedPackageId(pkg.id)}
            >
              <CardContent className="p-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-foreground">{pkg.name}</p>
                  <div className="flex gap-2 mt-1">
                    <Badge variant="secondary">{pkg.speed_mbps} Mbps</Badge>
                    <Badge variant="outline">{formatDuration(pkg.duration_minutes)}</Badge>
                  </div>
                </div>
                <p className="text-xl font-bold text-primary">
                  {formatKES(pkg.price_kes)}
                </p>
              </CardContent>
            </Card>
          ))}
          {packages?.length === 0 && (
            <p className="text-center text-muted-foreground text-sm">No packages available.</p>
          )}
        </div>
      )}

      {/* Phone input */}
      <div className="w-full max-w-sm space-y-2 mb-4">
        <label className="text-sm font-medium text-foreground">
          Your M-Pesa phone number
        </label>
        <Input
          type="tel"
          placeholder="0712 345 678"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="text-lg h-12"
        />
        {phoneError && (
          <p className="text-destructive text-sm">{phoneError}</p>
        )}
      </div>

      {/* Pay button */}
      <Button
        className="w-full max-w-sm h-14 text-lg bg-primary hover:bg-primary/90 text-primary-foreground"
        disabled={!selectedPackageId || !phone || stkMutation.isPending}
        onClick={handlePay}
      >
        {stkMutation.isPending ? (
          <><Loader2 className="animate-spin mr-2" /> Sending M-Pesa prompt...</>
        ) : (
          <><Zap className="mr-2" />
            Pay {selectedPackage ? formatKES(selectedPackage.price_kes) : ''} via M-Pesa
          </>
        )}
      </Button>

      {stkMutation.isError && (
        <p className="text-destructive text-sm mt-3 text-center">
          Something went wrong. Please try again.
        </p>
      )}

      <p className="text-xs text-muted-foreground mt-6 text-center">
        You will receive an M-Pesa prompt on your phone.<br />
        Enter your PIN to complete payment.
      </p>

      {/* Customer Portal Link */}
      <div className="mt-8 border-t border-border w-full max-w-sm pt-4 text-center">
        <p className="text-sm text-muted-foreground mb-2">Already have an account?</p>
        <Button 
          variant="outline" 
          className="w-full text-primary border-primary hover:bg-primary/10"
          onClick={() => window.location.href = '/login'}
        >
          Manage My Account
        </Button>
      </div>
    </div>
  )
}

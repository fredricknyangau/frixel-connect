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
  const [existingVoucher, setExistingVoucher] = useState('')
  const [showVoucherInput, setShowVoucherInput] = useState(false)

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
      {/* Toggle between Buy and Use Voucher */}
      <div className="w-full max-w-sm flex rounded-lg border bg-card p-1 mb-6">
        <button
          className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
            !showVoucherInput
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setShowVoucherInput(false)}
        >
          Buy WiFi Package
        </button>
        <button
          className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
            showVoucherInput
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setShowVoucherInput(true)}
        >
          Use Existing Voucher
        </button>
      </div>

      {showVoucherInput ? (
        <div className="w-full max-w-sm space-y-4">
          <p className="text-muted-foreground mb-6 text-center text-sm">
            Enter your voucher code below to connect to the internet
          </p>
          <Card>
            <CardContent className="p-4 space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Voucher Code / PIN
                </label>
                <Input
                  type="text"
                  placeholder="e.g. ABCDEFGHJK"
                  value={existingVoucher}
                  onChange={(e) => setExistingVoucher(e.target.value.toUpperCase().trim())}
                  className="text-lg h-12 text-center font-mono tracking-widest uppercase"
                />
              </div>
              <Button
                className="w-full h-12 text-md bg-primary hover:bg-primary/90 text-primary-foreground"
                disabled={!existingVoucher}
                onClick={() => onVoucherReceived(existingVoucher)}
              >
                Connect to Internet
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : (
        <>
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
        </>
      )}

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

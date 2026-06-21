import { useState, useEffect } from 'react'
import { useHotspotPackages } from '../../hooks/useHotspotPackages'
import { useHotspotSTKPush } from '../../hooks/useHotspotPayment'
import { formatKES } from '../../lib/utils'
import { formatDuration } from '../../lib/formatDuration'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Card, CardContent } from '../ui/card'
import { Badge } from '../ui/badge'
import { Loader2, Zap, AlertTriangle, Wifi, X, MessageSquare, Video, Sparkles, Smartphone, Check } from 'lucide-react'
import { toast } from 'sonner'
import PaymentPolling from './PaymentPolling'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../ui/dialog'
import { api } from '../../lib/api'


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
  const [showTips, setShowTips] = useState(false)
  const [savedVoucher, setSavedVoucher] = useState<string | null>(() => localStorage.getItem('active_wifi_voucher'))
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)
  const [isTrialModalOpen, setIsTrialModalOpen] = useState(false)
  const [trialPhone, setTrialPhone] = useState('')
  const [trialPhoneError, setTrialPhoneError] = useState('')
  const [isTrialLoading, setIsTrialLoading] = useState(false)
  const [latency, setLatency] = useState<number | null>(null)
  const [pingError, setPingError] = useState(false)

  useEffect(() => {
    const checkPing = async () => {
      const start = Date.now()
      try {
        await api.get(`/hotspot/packages`, { params: { tenant_id: tenantId } })
        setLatency(Date.now() - start)
        setPingError(false)
      } catch (err) {
        setLatency(Date.now() - start)
        setPingError(false)
      }
    }
    checkPing()
    const interval = setInterval(checkPing, 15000)
    return () => clearInterval(interval)
  }, [tenantId])

  const handleActivateTrial = async () => {
    const kenyanPhone = /^(?:0|254|\+254)[17]\d{8}$/
    if (!kenyanPhone.test(trialPhone)) {
      setTrialPhoneError('Enter a valid Kenyan phone number (e.g. 0712 345 678)')
      return
    }
    setTrialPhoneError('')
    setIsTrialLoading(true)
    try {
      const response = await api.post<{ voucher_code: string }>('/hotspot/trial', {
        phone: trialPhone,
        tenant_id: tenantId,
        mac_address: macAddress
      })
      const code = response.data.voucher_code
      localStorage.setItem('active_wifi_voucher', code)
      toast.success("Free trial activated! Connecting...")
      setIsTrialModalOpen(false)
      setTimeout(() => onVoucherReceived(code), 1000)
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || "You have already claimed a free trial or an error occurred."
      toast.error(errorDetail)
    } finally {
      setIsTrialLoading(false)
    }
  }

  const selectedPackage = packages?.find(p => p.id === selectedPackageId)


  const stkMutation = useHotspotSTKPush()

  const getSpeedIcon = (speed: number) => {
    if (speed <= 2) return <MessageSquare className="h-3 w-3 text-muted-foreground" />
    if (speed <= 7) return <Video className="h-3 w-3 text-blue-500" />
    return <Zap className="h-3 w-3 text-amber-500 fill-amber-500 animate-pulse" />
  }

  const getSpeedDescription = (speed: number) => {
    if (speed <= 2) return "Chatting & browsing"
    if (speed <= 7) return "HD streaming & video"
    return "Ultra-fast / gaming"
  }

  const handleClearSavedVoucher = (e: React.MouseEvent) => {
    e.stopPropagation()
    localStorage.removeItem('active_wifi_voucher')
    setSavedVoucher(null)
    toast.success('Saved voucher cleared')
  }

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
        setIsCheckoutOpen(false)
      }
    })
  }

  // Once STK push is initiated, show the polling screen
  if (paymentId && selectedPackage) {
    return (
      <PaymentPolling
        paymentId={paymentId}
        onConfirmed={(code) => {
          localStorage.setItem('active_wifi_voucher', code)
          onVoucherReceived(code)
        }}
        packagePrice={selectedPackage.price_kes}
        packageName={selectedPackage.name}
      />
    )
  }

  return (
    <div className="min-h-screen bg-muted/50 flex flex-col items-center justify-start p-4 pt-8">
      {/* Network Status & Ping Latency indicator */}
      <div className="w-full max-w-sm mb-3 flex items-center justify-between text-[11px] text-muted-foreground bg-card px-3 py-2 rounded-lg border">
        <div className="flex items-center gap-1.5 font-medium">
          <span className={`h-2 w-2 rounded-full ${pingError ? 'bg-destructive animate-ping' : 'bg-green-500 animate-pulse'}`} />
          {pingError ? 'System Offline' : 'System Online'}
        </div>
        <div>
          {latency !== null && !pingError ? `Ping: ${latency}ms` : 'Checking latency...'}
        </div>
      </div>

      {/* CNA Browser Warning Banner */}
      <div className="w-full max-w-sm mb-4 bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 p-3 rounded-lg text-xs flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold">Keep this window open!</span> Closing this page or pressing "Cancel" will disconnect you from the WiFi.
        </div>
      </div>


      {/* Saved active voucher reconnect */}
      {savedVoucher && (
        <Card className="w-full max-w-sm border-primary/30 bg-primary/5 mb-4 hover:border-primary/50 transition-all">
          <CardContent className="p-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="bg-primary/10 p-2 rounded-lg text-primary">
                <Wifi className="h-5 w-5" />
              </div>
              <div className="text-left">
                <p className="text-xs font-semibold text-foreground">Saved WiFi Voucher</p>
                <p className="font-mono text-sm font-bold text-primary tracking-wider">{savedVoucher}</p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                size="sm"
                className="h-8 text-xs font-semibold"
                onClick={() => onVoucherReceived(savedVoucher)}
              >
                Reconnect
              </Button>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={handleClearSavedVoucher}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

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
                onClick={() => {
                  localStorage.setItem('active_wifi_voucher', existingVoucher)
                  onVoucherReceived(existingVoucher)
                }}
              >
                Connect to Internet
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : (
        <>
          <p className="text-muted-foreground mb-6 text-center text-sm">
            Select a plan to get online instantly
          </p>

          {/* Package cards */}
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="animate-spin text-primary w-8 h-8" />
            </div>
          ) : (
            <div className="w-full max-w-sm space-y-3 mb-6">
              {packages?.map(pkg => {
                const maxSpeed = Math.max(...(packages.map(p => p.speed_mbps) || [0]));
                const isFastest = pkg.speed_mbps === maxSpeed && maxSpeed > 0;
                const isSelected = selectedPackageId === pkg.id;
                return (
                  <Card
                    key={pkg.id}
                    className={`cursor-pointer transition-all border-2 relative overflow-hidden ${
                      isSelected
                        ? 'border-primary bg-primary/10 shadow-md scale-[1.01]'
                        : isFastest
                        ? 'border-primary/40 bg-card hover:border-primary/60 shadow-sm'
                        : 'border-border bg-card hover:border-muted-foreground/30'
                    }`}
                    onClick={() => {
                      setSelectedPackageId(pkg.id)
                      setIsCheckoutOpen(true)
                    }}
                  >
                    {isFastest && (
                      <div className="absolute top-0 right-0 bg-primary text-primary-foreground text-[10px] font-bold px-2 py-0.5 rounded-bl shadow-sm flex items-center gap-1">
                        <Sparkles className="h-2.5 w-2.5 animate-pulse" /> Best Value
                      </div>
                    )}
                    <CardContent className="p-4 flex items-center justify-between">
                      <div className="text-left">
                        <p className="font-semibold text-foreground">{pkg.name}</p>
                        <div className="flex flex-wrap gap-2 mt-1.5 items-center">
                          <Badge variant="secondary" className="text-[10px] py-0 px-1.5 flex items-center gap-1">
                            {getSpeedIcon(pkg.speed_mbps)}
                            {pkg.speed_mbps} Mbps
                          </Badge>
                          <Badge variant="outline" className="text-[10px] py-0 px-1.5">
                            {formatDuration(pkg.duration_minutes)}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground">
                            • {getSpeedDescription(pkg.speed_mbps)}
                          </span>
                        </div>
                      </div>
                      <p className="text-xl font-bold text-primary shrink-0 ml-3">
                        {formatKES(pkg.price_kes)}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
              {packages?.length === 0 && (
                <p className="text-center text-muted-foreground text-sm">No packages available.</p>
              )}
            </div>
          )}

          {/* Free Trial Button Trigger */}
          <div className="text-center mt-3 mb-5 w-full max-w-sm">
            <button
              onClick={() => setIsTrialModalOpen(true)}
              className="text-xs text-primary font-semibold hover:underline flex items-center justify-center gap-1 mx-auto py-1 px-3 border border-primary/20 bg-primary/5 hover:bg-primary/10 rounded-full transition-all"
            >
              <Sparkles className="h-3 w-3 animate-pulse text-amber-500 fill-amber-500" /> 
              Want to test the speed? Try 10 Mins Free
            </button>
          </div>

          {/* Free Trial Modal Dialog */}
          <Dialog open={isTrialModalOpen} onOpenChange={setIsTrialModalOpen}>
            <DialogContent className="sm:max-w-sm">
              <DialogHeader className="text-left">
                <DialogTitle className="text-xl font-bold">Claim Free Trial</DialogTitle>
                <DialogDescription className="text-xs">
                  Enjoy 10 minutes of free internet access at 2 Mbps. Limit: once every 24 hours.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-3 text-left">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-foreground">
                    Your Phone Number
                  </label>
                  <Input
                    type="tel"
                    placeholder="e.g. 0712 345 678"
                    value={trialPhone}
                    onChange={(e) => setTrialPhone(e.target.value)}
                    className="text-lg h-12"
                  />
                  {trialPhoneError && (
                    <p className="text-destructive text-xs">{trialPhoneError}</p>
                  )}
                </div>
              </div>

              <DialogFooter className="flex flex-col gap-2">
                <Button
                  className="w-full h-12 text-md font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all hover:scale-[1.01]"
                  disabled={!trialPhone || isTrialLoading}
                  onClick={handleActivateTrial}
                >
                  {isTrialLoading ? (
                    <><Loader2 className="animate-spin mr-2 h-4 w-4" /> Activating trial...</>
                  ) : (
                    <>Activate 10 Mins Free</>
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Checkout Modal Dialog */}
          <Dialog open={isCheckoutOpen} onOpenChange={setIsCheckoutOpen}>
            <DialogContent className="sm:max-w-sm">
              <DialogHeader className="text-left">
                <DialogTitle className="text-xl font-bold">Activate {selectedPackage?.name}</DialogTitle>
                <DialogDescription className="text-xs">
                  Pay via M-Pesa to connect to the internet.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-3 text-left">
                <div className="bg-muted/40 p-3 rounded-lg flex justify-between items-center text-xs border">
                  <div>
                    <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Speed / Duration</span>
                    <span className="font-semibold text-foreground">{selectedPackage?.speed_mbps} Mbps for {selectedPackage ? formatDuration(selectedPackage.duration_minutes) : ''}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Amount</span>
                    <span className="font-bold text-primary text-sm">{selectedPackage ? formatKES(selectedPackage.price_kes) : ''}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-semibold text-foreground">
                    Your M-Pesa Phone Number
                  </label>
                  <Input
                    type="tel"
                    placeholder="e.g. 0712 345 678"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="text-lg h-12"
                  />
                  {phoneError && (
                    <p className="text-destructive text-xs">{phoneError}</p>
                  )}
                </div>
              </div>

              <div className="flex flex-col gap-2 mt-2">
                <Button
                  className="w-full h-12 text-md font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all hover:scale-[1.01]"
                  disabled={!phone || stkMutation.isPending}
                  onClick={handlePay}
                >
                  {stkMutation.isPending ? (
                    <><Loader2 className="animate-spin mr-2 h-4 w-4" /> Requesting payment PIN...</>
                  ) : (
                    <><Zap className="mr-2 h-4 w-4" /> Pay {selectedPackage ? formatKES(selectedPackage.price_kes) : ''}</>
                  )}
                </Button>
                
                {stkMutation.isError && (
                  <p className="text-destructive text-xs text-center font-medium mt-1">
                    Failed to send prompt. Please try again.
                  </p>
                )}

                <p className="text-[10px] text-muted-foreground text-center mt-2 leading-relaxed">
                  You will receive an M-Pesa STK push prompt on your phone.<br />
                  Enter your PIN to complete the connection.
                </p>
              </div>
            </DialogContent>
          </Dialog>
        </>
      )}

      {/* Local Partner Deals (Sponsor Ad) */}
      <Card className="w-full max-w-sm bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5 border border-primary/20 p-4 text-left mt-6 relative overflow-hidden group">
        <CardContent className="p-0 space-y-3">
          <div className="flex justify-between items-start">
            <Badge className="bg-primary/20 text-primary hover:bg-primary/25 border-none text-[9px] uppercase font-bold tracking-wider px-1.5 py-0">
              Partner Deal
            </Badge>
            <Sparkles className="h-4 w-4 text-primary animate-pulse" />
          </div>
          <div className="space-y-1">
            <h4 className="font-bold text-sm text-foreground">Get 10% Off at Coffee Bistro!</h4>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Connect to this WiFi network, select any plan, and show your active voucher screen at Coffee Bistro next door to redeem your discount.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Connection Tips / Help & Diagnostics Accordion */}
      <div className="w-full max-w-sm mt-4">
        <button
          onClick={() => setShowTips(!showTips)}
          className="w-full flex items-center justify-between text-xs text-muted-foreground hover:text-foreground transition-colors p-2 border border-dashed rounded-lg bg-card/50"
        >
          <span>Connection issues or self diagnostics?</span>
          <span className="text-sm font-semibold">{showTips ? '−' : '+'}</span>
        </button>
        {showTips && (
          <Card className="mt-2 border bg-card/85 text-left divide-y divide-border">
            <CardContent className="p-4 space-y-3 text-xs text-muted-foreground leading-relaxed">
              <div>
                <p className="font-semibold text-foreground mb-1">💡 Disconnecting frequently?</p>
                <p>If you turn off Wi-Fi or leave the area, the network terminates active sessions. Keep your voucher code safe to reuse it on the <b>"Use Existing Voucher"</b> tab.</p>
              </div>
              <div className="pt-2 border-t">
                <p className="font-semibold text-foreground mb-1 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                  CNA / Private MAC Address Issue
                </p>
                <p>To let the Wi-Fi recognize your device and log you in automatically next time:</p>
                <ol className="list-decimal pl-4 mt-1 space-y-1">
                  <li>Go to your phone's <b>Settings</b> &gt; <b>Wi-Fi</b>.</li>
                  <li>Tap the info icon <b>(i)</b> next to this Wi-Fi network.</li>
                  <li>Disable <b>"Private Wi-Fi Address"</b> or <b>"Use Randomized MAC"</b> (change it to <b>"Use Device MAC"</b>).</li>
                </ol>
              </div>
            </CardContent>
            
            <CardContent className="p-4 space-y-3 text-xs text-muted-foreground">
              <p className="font-semibold text-foreground flex items-center gap-1.5">
                <Smartphone className="h-3.5 w-3.5 text-primary" />
                Self-Service Connection Diagnostics
              </p>
              <div className="space-y-2">
                <div className="flex items-center justify-between bg-muted/40 p-2 rounded border text-[11px]">
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green-500" /> Router Connection
                  </span>
                  <span className="text-green-600 font-bold dark:text-green-400">ACTIVE</span>
                </div>
                <div className="flex items-center justify-between bg-muted/40 p-2 rounded border text-[11px]">
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green-500" /> IP Address Assigned
                  </span>
                  <span className="font-mono text-muted-foreground">{clientIp || '10.10.10.X'}</span>
                </div>
                <div className="flex items-center justify-between bg-muted/40 p-2 rounded border text-[11px]">
                  <span className="flex items-center gap-1.5">
                    <Check className="h-3.5 w-3.5 text-green-500" /> DNS Servers Configured
                  </span>
                  <span className="text-muted-foreground">Automatic</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

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

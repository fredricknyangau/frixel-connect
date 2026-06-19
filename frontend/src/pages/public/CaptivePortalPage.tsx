import { useSearchParams } from 'react-router-dom'
import { useState } from 'react'
import BuyPackageFlow from '../../components/hotspot/BuyPackageFlow'
import HotspotLoginRedirect from '../../components/hotspot/HotspotLoginRedirect'

export default function CaptivePortalPage() {
  const [searchParams] = useSearchParams()
  const [voucherCode, setVoucherCode] = useState<string | null>(null)

  // These come from MikroTik's redirect
  const tenantId = searchParams.get('tenant_id') ?? ''
  const mac = searchParams.get('mac') ?? ''
  const ip = searchParams.get('ip') ?? ''
  const linkLogin = searchParams.get('link-login') ?? ''
  const linkOrig = searchParams.get('link-orig') ?? 'http://google.com'

  // Once we have a voucher code, show the login redirect
  if (voucherCode) {
    return (
      <HotspotLoginRedirect
        voucherCode={voucherCode}
        linkLogin={linkLogin}
        linkOrig={linkOrig}
      />
    )
  }

  if (!tenantId) {
    return (
      <div className="min-h-screen bg-muted/50 flex flex-col items-center justify-center p-4">
        <div className="bg-card p-6 rounded-lg shadow-md max-w-sm text-center border-t-4 border-destructive">
          <h2 className="text-xl font-bold text-foreground mb-2">Configuration Error</h2>
          <p className="text-muted-foreground text-sm">
            This hotspot is missing its tenant ID configuration. Please contact the network administrator.
          </p>
        </div>
      </div>
    )
  }

  return (
    <BuyPackageFlow
      tenantId={tenantId}
      macAddress={mac}
      clientIp={ip}
      onVoucherReceived={(code) => setVoucherCode(code)}
    />
  )
}

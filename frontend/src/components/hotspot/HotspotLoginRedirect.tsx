import { useEffect } from 'react'
import { CheckCircle2 } from 'lucide-react'

interface Props {
  voucherCode: string
  linkLogin: string
  linkOrig: string
}

export default function HotspotLoginRedirect({ voucherCode, linkLogin, linkOrig }: Props) {
  // Build the MikroTik hotspot login URL safely handling existing query params
  let loginUrl = ''
  if (linkLogin) {
    try {
      const url = new URL(linkLogin)
      url.searchParams.set('username', voucherCode)
      url.searchParams.set('password', voucherCode)
      if (linkOrig) {
        url.searchParams.set('dst', linkOrig)
      }
      url.hostname = '10.10.10.1'
      loginUrl = url.toString()
    } catch (e) {
      // Fallback if linkLogin is not a valid URL
      const separator = linkLogin.includes('?') ? '&' : '?'
      loginUrl = `${linkLogin}${separator}username=${encodeURIComponent(voucherCode)}&password=${encodeURIComponent(voucherCode)}&dst=${encodeURIComponent(linkOrig)}`
    }
  }

  useEffect(() => {
    if (!loginUrl) {
      // No link-login param means the user opened the portal directly
      // (e.g. testing in a browser not on the hotspot LAN)
      // Just show the voucher code — nothing to redirect to
      return
    }

    // Redirect the phone's browser to MikroTik's login endpoint after a short delay
    // so they have time to see their PIN.
    const timer = setTimeout(() => {
      window.location.href = loginUrl
    }, 5000)

    return () => clearTimeout(timer)
  }, [loginUrl])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 text-center">
      <CheckCircle2 className="text-primary w-16 h-16 mb-4" />
      <h2 className="text-2xl font-bold text-foreground">You're connected!</h2>
      <p className="text-muted-foreground mt-2">Redirecting you to the internet...</p>

      <div className="mt-6 p-4 bg-muted rounded-lg w-full max-w-sm">
        <p className="text-sm text-foreground mb-2">
          Your PIN has been sent via SMS.
          You can use this PIN along with your phone number to log into the <b>Customer Portal</b>.
        </p>
        <p className="text-xs text-muted-foreground mb-1 mt-4">Voucher Code / PIN</p>
        <p className="font-mono text-xl font-bold text-foreground tracking-widest bg-card p-2 border border-border rounded">
          {voucherCode}
        </p>
      </div>

      {!linkLogin && (
        <p className="text-xs text-muted-foreground mt-4">
          Connect to the WiFi network and open this page again to go online.
        </p>
      )}
      
      {linkLogin && (
        <div className="mt-6">
          <button 
            className="text-sm text-primary underline hover:text-primary/90"
            onClick={() => window.location.href = loginUrl}
          >
            Click here if you are not redirected automatically
          </button>
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, Check, ArrowRight, Share2, Printer, AlertTriangle } from 'lucide-react'
import { Button } from '../ui/button'
import { toast } from 'sonner'

interface Props {
  voucherCode: string
  linkLogin: string
  linkOrig: string
}

// Fallback clipboard copying helper for non-secure HTTP contexts
const copyToClipboard = (text: string): Promise<void> => {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text)
  }
  
  return new Promise((resolve, reject) => {
    try {
      const textArea = document.createElement("textarea")
      textArea.value = text
      textArea.style.top = "0"
      textArea.style.left = "0"
      textArea.style.position = "fixed"
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      
      const successful = document.execCommand("copy")
      document.body.removeChild(textArea)
      
      if (successful) {
        resolve()
      } else {
        reject(new Error("Fallback copy failed"))
      }
    } catch (err) {
      reject(err)
    }
  })
}

export default function HotspotLoginRedirect({ voucherCode, linkLogin, linkOrig }: Props) {
  const [copied, setCopied] = useState(false)

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

  const handleCopy = () => {
    copyToClipboard(voucherCode).then(() => {
      setCopied(true)
      toast.success("Voucher PIN copied!")
      setTimeout(() => setCopied(false), 2000)
    }).catch(() => {
      toast.error("Failed to copy PIN. Copy it manually from the screen.")
    })
  }

  // Auto-copy on mount
  useEffect(() => {
    copyToClipboard(voucherCode).then(() => {
      toast.success("Voucher PIN automatically copied to clipboard!")
    }).catch(() => {
      // Silent catch for initial user action requirement in some browsers
    })
  }, [voucherCode])

  useEffect(() => {
    if (!loginUrl) {
      // No link-login param means the user opened the portal directly
      return
    }

    // Redirect the phone's browser to MikroTik's login endpoint after a short delay
    const timer = setTimeout(() => {
      window.location.href = loginUrl
    }, 8000) // 8 seconds to allow saving/sharing the ticket

    return () => clearTimeout(timer)
  }, [loginUrl])

  const handlePrint = () => {
    window.print()
  }

  const handleShareWhatsApp = () => {
    const text = `My WiFi Voucher PIN is: *${voucherCode}* 📶\n\nUse this PIN to connect or log back in at the captive portal.`
    const url = `https://wa.me/?text=${encodeURIComponent(text)}`
    window.open(url, '_blank')
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-start p-4 pt-10 text-center bg-muted/50 print:bg-white print:p-0">
      {/* Main Ticket Receipt Wrapper */}
      <div className="relative bg-card rounded-2xl shadow-xl border w-full max-w-sm overflow-visible flex flex-col print:shadow-none print:border-none print:w-full">
        
        {/* Top Segment: Branding & Confirmation */}
        <div className="p-6 pb-4 flex flex-col items-center">
          <div className="bg-primary/10 text-primary p-3 rounded-full mb-3 animate-pulse">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-extrabold text-foreground tracking-tight">Voucher Activated</h2>
          <p className="text-xs text-muted-foreground mt-1">Payment successful. Access is provisioned.</p>

          <div className="w-full mt-4 flex items-center justify-between text-xs text-muted-foreground bg-muted/30 rounded-lg p-2.5 border border-dashed">
            <span>Network Status</span>
            <span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Connected
            </span>
          </div>
        </div>

        {/* Ticket Notch Divider */}
        <div className="relative w-full flex items-center">
          {/* Left Notch */}
          <div className="absolute left-0 -translate-x-1/2 w-5 h-5 rounded-full bg-muted/50 border border-border z-10 print:hidden" />
          
          {/* Dashed Line */}
          <div className="w-full border-t-2 border-dashed border-border" />
          
          {/* Right Notch */}
          <div className="absolute right-0 translate-x-1/2 w-5 h-5 rounded-full bg-muted/50 border border-border z-10 print:hidden" />
        </div>

        {/* Middle Segment: PIN Display */}
        <div className="p-6 py-4 space-y-4">
          <div className="space-y-1.5">
            <span className="text-[10px] text-muted-foreground font-bold uppercase tracking-wider block">
              Your WiFi Voucher PIN
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-2xl font-black text-primary tracking-widest bg-primary/5 p-3 border-2 border-primary/20 rounded-xl flex-1 text-center uppercase select-all shadow-inner">
                {voucherCode}
              </span>
              <Button
                size="icon"
                variant="outline"
                className="h-14 w-14 shrink-0 rounded-xl border-2 hover:bg-muted"
                onClick={handleCopy}
                title="Copy PIN"
              >
                {copied ? (
                  <Check className="h-5 w-5 text-green-500" />
                ) : (
                  <Copy className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>

          {/* Screenshot / Print Warning Alert Box */}
          <div className="bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 p-3 rounded-xl text-left text-xs flex gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold">Important Notice</span>
              <p className="leading-normal">
                Take a <span className="font-semibold underline">screenshot</span> or <span className="font-semibold underline">print</span> this voucher ticket now. You will need this PIN to reconnect if you are logged out.
              </p>
            </div>
          </div>
        </div>

        {/* Ticket Notch Divider 2 */}
        <div className="relative w-full flex items-center">
          {/* Left Notch */}
          <div className="absolute left-0 -translate-x-1/2 w-5 h-5 rounded-full bg-muted/50 border border-border z-10 print:hidden" />
          
          {/* Dashed Line */}
          <div className="w-full border-t-2 border-dashed border-border" />
          
          {/* Right Notch */}
          <div className="absolute right-0 translate-x-1/2 w-5 h-5 rounded-full bg-muted/50 border border-border z-10 print:hidden" />
        </div>

        {/* Bottom Segment: Sharing & Actions */}
        <div className="p-6 pt-4 space-y-3 print:hidden">
          {/* WhatsApp & Print Actions */}
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              className="h-10 text-xs font-semibold border-2 flex items-center justify-center gap-1.5"
              onClick={handlePrint}
            >
              <Printer className="h-4 w-4" /> Print Ticket
            </Button>
            <Button
              variant="outline"
              className="h-10 text-xs font-semibold border-2 flex items-center justify-center gap-1.5 hover:bg-emerald-500/10 hover:text-emerald-600 hover:border-emerald-500/30"
              onClick={handleShareWhatsApp}
            >
              <Share2 className="h-4 w-4" /> Share on WA
            </Button>
          </div>

          {/* Primary Connection Redirection */}
          {linkLogin ? (
            <div className="space-y-2 pt-2">
              <Button
                className="w-full h-12 text-sm font-bold bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all hover:scale-[1.01] rounded-xl flex items-center justify-center gap-1.5"
                onClick={() => window.location.href = loginUrl}
              >
                Go Online Now <ArrowRight className="h-4 w-4" />
              </Button>
              <p className="text-[10px] text-muted-foreground">
                Redirecting automatically in a few seconds...
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground pt-2">
              Make sure you are connected to the Wi-Fi network.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

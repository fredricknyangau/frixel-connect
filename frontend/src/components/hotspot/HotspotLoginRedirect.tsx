import { useEffect, useState } from 'react'
import { CheckCircle2, Copy, Check, ArrowRight, Share2, Printer, AlertTriangle } from 'lucide-react'
import { Button } from '../ui/button'
import { toast } from 'sonner'

interface Props {
  voucherCode: string
  linkLogin: string
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

export default function HotspotLoginRedirect({ voucherCode, linkLogin }: Props) {
  const [copied, setCopied] = useState(false)

  const [isLoggingIn, setIsLoggingIn] = useState(false)
  const [isOnline, setIsOnline] = useState(false)

  const performLogin = async () => {
    if (!linkLogin) return;
    if (isLoggingIn || isOnline) return;

    setIsLoggingIn(true);
    const baseUrl = linkLogin.split('?')[0];
    const url = baseUrl.startsWith('http') ? baseUrl : `http://${baseUrl}`;

    try {
      // Perform AJAX login to Mikrotik to avoid navigating the CNA away.
      // The OS background captive portal probe will now succeed and close the CNA.
      await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `username=${encodeURIComponent(voucherCode)}&password=${encodeURIComponent(voucherCode)}`,
        mode: 'no-cors'
      });
    } catch (e) {
      console.error('Login failed', e);
    }

    setIsLoggingIn(false);
    setIsOnline(true);
  };

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
    if (!linkLogin) {
      // No link-login param means the user opened the portal directly
      return
    }

    // Redirect the phone's browser to MikroTik's login endpoint after a short delay
    const timer = setTimeout(() => {
      performLogin()
    }, 3000) // 3 seconds to allow seeing the success state

    return () => clearTimeout(timer)
  }, [linkLogin])

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
              {isOnline ? (
                <div className="w-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 p-3 rounded-xl flex flex-col items-center justify-center gap-1">
                  <CheckCircle2 className="h-6 w-6 mb-1" />
                  <span className="font-bold text-sm">You are Connected!</span>
                  <p className="text-[10px] text-center leading-relaxed font-medium">
                    The WiFi icon will appear at the top of your screen shortly. 
                    <br/>You may now click "Done" or close this window.
                  </p>
                </div>
              ) : (
                <>
                  <Button
                    className="w-full h-12 text-sm font-bold bg-primary hover:bg-primary/90 text-primary-foreground shadow-md transition-all hover:scale-[1.01] rounded-xl flex items-center justify-center gap-1.5"
                    onClick={performLogin}
                    disabled={isLoggingIn}
                  >
                    {isLoggingIn ? 'Connecting...' : <>Go Online Now <ArrowRight className="h-4 w-4" /></>}
                  </Button>
                  <p className="text-[10px] text-muted-foreground">
                    Connecting automatically in a few seconds...
                  </p>
                </>
              )}
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

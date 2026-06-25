import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  Wifi, Menu, Phone, Monitor, Users, Zap, 
  Terminal, Copy, CheckCircle, Shield, 
  RefreshCw, BarChart3, MessageSquare, 
  Lock, Receipt, CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const jsonLdData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "name": "ZealSync",
        "url": "https://zealsync.dev",
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "Nairobi",
          "addressCountry": "KE"
        }
      },
      {
        "@type": "SoftwareApplication",
        "name": "ZealSync",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web",
        "offers": [
          {
            "@type": "Offer",
            "price": "1500",
            "priceCurrency": "KES",
            "name": "Starter"
          },
          {
            "@type": "Offer",
            "price": "2500",
            "priceCurrency": "KES",
            "name": "Growth"
          }
        ]
      }
    ]
  };

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground dark">
      <Helmet>
        <title>ZealSync — WiFi & Fiber Billing Software for Kenyan ISPs | M-Pesa + MikroTik</title>
        <meta name="description" content="Automate your Kenyan ISP billing. M-Pesa STK Push + MikroTik hotspot vouchers + PPPoE fiber billing. One platform for hotspot and fiber ISPs. Free 30-day pilot." />
        <link rel="canonical" href="https://zealsync.dev/" />
        <meta property="og:title" content="ZealSync — WiFi Billing for Kenyan ISPs" />
        <meta property="og:description" content="Automate your Kenyan ISP billing. M-Pesa STK Push + MikroTik hotspot vouchers + PPPoE fiber billing. One platform for hotspot and fiber ISPs. Free 30-day pilot." />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://zealsync.dev" />
        <script type="application/ld+json">
          {JSON.stringify(jsonLdData)}
        </script>
      </Helmet>

      {/* SECTION 1: NAVBAR */}
      <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${scrolled ? 'bg-background shadow-lg border-b border-border/50' : 'bg-transparent'}`}>
        <div className="container mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Wifi className="h-6 w-6 text-primary" />
            <span className="text-xl font-bold tracking-tight text-primary">ZealSync</span>
          </Link>
          
          <div className="hidden md:flex items-center gap-6">
            <button onClick={() => scrollToSection('hotspot')} className="text-sm font-medium hover:text-primary transition-colors">Hotspot</button>
            <button onClick={() => scrollToSection('fiber')} className="text-sm font-medium hover:text-primary transition-colors">Fiber</button>
            <button onClick={() => scrollToSection('pricing')} className="text-sm font-medium hover:text-primary transition-colors">Pricing</button>
            <Button variant="ghost" className="hover:bg-primary/10" render={<Link to="/login" />}>
              Sign In
            </Button>
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90" render={<Link to="/signup" />}>
              Start Free Trial
            </Button>
          </div>

          <div className="md:hidden">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger
                render={
                  <Button variant="ghost" size="icon">
                    <Menu className="h-6 w-6" />
                  </Button>
                }
              />
              <SheetContent side="right" className="flex flex-col gap-4 bg-background">
                <div className="flex items-center gap-2 mb-4">
                  <Wifi className="h-6 w-6 text-primary" />
                  <span className="text-xl font-bold text-primary">ZealSync</span>
                </div>
                <button
                  onClick={() => {
                    scrollToSection('hotspot');
                    setMobileMenuOpen(false);
                  }}
                  className="text-left text-lg font-medium py-2 border-b border-border"
                >
                  Hotspot
                </button>
                <button
                  onClick={() => {
                    scrollToSection('fiber');
                    setMobileMenuOpen(false);
                  }}
                  className="text-left text-lg font-medium py-2 border-b border-border"
                >
                  Fiber
                </button>
                <button
                  onClick={() => {
                    scrollToSection('pricing');
                    setMobileMenuOpen(false);
                  }}
                  className="text-left text-lg font-medium py-2 border-b border-border"
                >
                  Pricing
                </button>
                <Link
                  to="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-lg font-medium py-2 border-b border-border"
                >
                  Sign In
                </Link>
                <Link
                  to="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-lg font-medium py-2 text-primary"
                >
                  Start Free Trial
                </Link>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </nav>

      {/* SECTION 2: HERO */}
      <section className="pt-32 pb-20 px-4 md:px-6 relative overflow-hidden">
        {/* Decorative background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/10 rounded-full blur-[100px] -z-10 pointer-events-none" />
        
        <div className="container mx-auto max-w-4xl text-center">
          <div className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary mb-8 uppercase tracking-wider">
            Now supporting Hotspot + Fiber PPPoE
          </div>
          
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-extrabold tracking-tight mb-6">
            WiFi Billing Software Built for Kenyan ISPs
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground mb-10 max-w-2xl mx-auto leading-relaxed">
            From M-Pesa payment to internet access in under 60 seconds. Automate your hotspot vouchers and fiber subscriptions — no manual Winbox, no Excel sheets, no midnight calls.
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
            <Button size="lg" className="w-full sm:w-auto h-14 px-8 text-lg font-semibold bg-primary text-primary-foreground hover:bg-primary/90 rounded-full" render={<Link to="/signup" />}>
              Start Free Trial
            </Button>
            <Button size="lg" variant="outline" className="w-full sm:w-auto h-14 px-8 text-lg font-semibold rounded-full border-primary/20 hover:bg-primary/5" onClick={() => scrollToSection('demo')}>
              See It Live
            </Button>
          </div>

          {/* Hero Visual - SVG Diagram */}
          <div className="max-w-3xl mx-auto mb-12 bg-card border border-border/50 rounded-2xl p-6 shadow-2xl relative">
            <svg viewBox="0 0 800 250" className="w-full h-auto drop-shadow-lg" preserveAspectRatio="xMidYMid meet">
              <defs>
                <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="currentColor" className="text-primary" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="currentColor" className="text-primary" stopOpacity="0.8" />
                </linearGradient>
              </defs>
              
              {/* Phone (Left) */}
              <rect x="50" y="25" width="120" height="200" rx="16" fill="currentColor" className="text-background" stroke="currentColor" strokeWidth="4" />
              <rect x="58" y="33" width="104" height="184" rx="10" fill="currentColor" className="text-card" />
              <text x="110" y="80" textAnchor="middle" fill="currentColor" className="text-primary text-[14px] font-bold">ZealSync WiFi</text>
              <rect x="70" y="100" width="80" height="30" rx="6" fill="currentColor" className="text-primary/20" />
              <text x="110" y="120" textAnchor="middle" fill="currentColor" className="text-foreground text-[12px] font-bold">Pay KES 100</text>
              
              {/* Arrows & Process (Center) */}
              <g className="text-primary">
                <path d="M 230 125 L 530 125" stroke="currentColor" strokeWidth="2" strokeDasharray="6,6" fill="none" />
                <circle cx="380" cy="125" r="40" fill="url(#glow)" />
                <path d="M 370 110 L 390 125 L 370 140" stroke="currentColor" strokeWidth="3" fill="none" className="text-background" />
                <text x="380" y="190" textAnchor="middle" fill="currentColor" className="text-muted-foreground text-[12px] font-medium">M-Pesa → Voucher → Online</text>
              </g>

              {/* Router (Right) */}
              <rect x="590" y="85" width="140" height="80" rx="8" fill="currentColor" className="text-card" stroke="currentColor" strokeWidth="4" />
              <line x1="610" y1="50" x2="610" y2="85" stroke="currentColor" strokeWidth="4" />
              <line x1="710" y1="50" x2="710" y2="85" stroke="currentColor" strokeWidth="4" />
              <circle cx="700" cy="125" r="8" fill="#10b981" />
              <text x="645" y="130" textAnchor="middle" fill="currentColor" className="text-foreground text-[14px] font-bold">MikroTik</text>
            </svg>
          </div>

          {/* Trust Signals */}
          <div className="flex flex-col md:flex-row items-center justify-center gap-6 md:gap-12 text-sm font-medium text-muted-foreground">
            <div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-primary" /> No percentage cuts on your revenue</div>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-primary" /> Works with your existing MikroTik</div>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-primary" /> Free 30-day pilot</div>
          </div>
        </div>
      </section>

      {/* SECTION 3: THE PROBLEM */}
      <section id="the-problem" className="py-24 bg-muted/30 px-4 md:px-6">
        <div className="container mx-auto max-w-5xl text-center">
          <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">Sound familiar?</h2>
          <h3 className="text-3xl md:text-4xl font-bold mb-16">Running an ISP in Kenya shouldn't feel like this</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="bg-background border border-border/50 p-8 rounded-2xl shadow-sm text-left">
              <div className="bg-destructive/10 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <Phone className="h-6 w-6 text-destructive" />
              </div>
              <h4 className="text-xl font-bold mb-3">Midnight M-Pesa alerts</h4>
              <p className="text-muted-foreground">You wake up to 20 payment notifications and customers whose internet expired at 2 AM.</p>
            </div>
            
            <div className="bg-background border border-border/50 p-8 rounded-2xl shadow-sm text-left">
              <div className="bg-destructive/10 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <Monitor className="h-6 w-6 text-destructive" />
              </div>
              <h4 className="text-xl font-bold mb-3">3 hours in Winbox every day</h4>
              <p className="text-muted-foreground">Manually enabling PPPoE secrets and generating hotspot vouchers instead of growing your business.</p>
            </div>
            
            <div className="bg-background border border-border/50 p-8 rounded-2xl shadow-sm text-left">
              <div className="bg-destructive/10 w-12 h-12 rounded-xl flex items-center justify-center mb-6">
                <Users className="h-6 w-6 text-destructive" />
              </div>
              <h4 className="text-xl font-bold mb-3">Resellers calling for vouchers</h4>
              <p className="text-muted-foreground">Your agents in Kasarani, Eastlands, and Kibera can't operate without calling you first.</p>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 4: DUAL SERVICE OVERVIEW */}
      <section id="services" className="py-24 px-4 md:px-6">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">What ZealSync supports</h2>
            <h3 className="text-3xl md:text-4xl font-bold">One platform for both types of Kenyan ISP</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative">
            {/* Divider line on desktop */}
            <div className="hidden md:block absolute top-0 bottom-0 left-1/2 w-px bg-border/50 -translate-x-1/2" />

            {/* Left Card - Hotspot */}
            <div id="hotspot" className="bg-card border border-border rounded-3xl p-8 lg:p-12 shadow-sm relative overflow-hidden group hover:border-primary/50 transition-colors">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-bl-full -z-10 group-hover:scale-110 transition-transform" />
              <div className="flex items-center gap-4 mb-6">
                <div className="bg-primary/20 p-3 rounded-xl">
                  <Wifi className="h-8 w-8 text-primary" />
                </div>
                <span className="bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Hotspot</span>
              </div>
              <h4 className="text-2xl font-bold mb-4">Public WiFi & Captive Portal</h4>
              <p className="text-muted-foreground mb-8">For ISPs selling session-based WiFi access in estates, malls, matatus, cyber cafés, hotels, and student hostels. Customers pay per session — daily, weekly, or custom.</p>
              
              <div className="mb-8">
                <h5 className="font-semibold mb-4 text-foreground/90">How it works</h5>
                <ol className="space-y-4 text-sm text-muted-foreground">
                  <li className="flex gap-3"><span className="font-bold text-primary">1.</span> Customer joins your WiFi and opens any website</li>
                  <li className="flex gap-3"><span className="font-bold text-primary">2.</span> They see your ZealSync captive portal — select a plan and pay via M-Pesa STK Push</li>
                  <li className="flex gap-3"><span className="font-bold text-primary">3.</span> Voucher activates instantly. Internet access starts.</li>
                </ol>
              </div>

              <div className="mb-10">
                <h5 className="font-semibold mb-4 text-foreground/90">Key features</h5>
                <ul className="space-y-3 text-sm text-muted-foreground">
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-primary" /> M-Pesa STK Push — no manual payment collection</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-primary" /> MikroTik hotspot user created automatically</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-primary" /> Voucher code sent via SMS (Africa's Talking)</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-primary" /> Reseller wallet — agents sell autonomously</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-primary" /> Speed tiers: 10 / 20 / 50 Mbps profiles</li>
                </ul>
              </div>

              <Button className="w-full bg-primary text-primary-foreground hover:bg-primary/90 h-12 rounded-full" render={<Link to="/signup?service=hotspot" />}>
                Set up hotspot billing
              </Button>
            </div>

            {/* Right Card - Fiber */}
            <div id="fiber" className="bg-card border border-border rounded-3xl p-8 lg:p-12 shadow-sm relative overflow-hidden group hover:border-[#6366f1]/50 transition-colors">
              <div className="absolute top-0 right-0 w-32 h-32 bg-[#6366f1]/10 rounded-bl-full -z-10 group-hover:scale-110 transition-transform" />
              <div className="flex items-center gap-4 mb-6">
                <div className="bg-[#6366f1]/20 p-3 rounded-xl">
                  <Zap className="h-8 w-8 text-[#6366f1]" />
                </div>
                <span className="bg-[#6366f1] text-white px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Fiber / PPPoE</span>
              </div>
              <h4 className="text-2xl font-bold mb-4">Home Fiber & CPE Broadband</h4>
              <p className="text-muted-foreground mb-8">For ISPs providing fixed home internet via fiber, wireless CPE, or LTE routers. Monthly subscriptions with automated renewal reminders and instant suspension on non-payment.</p>
              
              <div className="mb-8">
                <h5 className="font-semibold mb-4 text-foreground/90">How it works</h5>
                <ol className="space-y-4 text-sm text-muted-foreground">
                  <li className="flex gap-3"><span className="font-bold text-[#6366f1]">1.</span> Customer subscribes to a monthly package</li>
                  <li className="flex gap-3"><span className="font-bold text-[#6366f1]">2.</span> Auto-renewal reminder sent 3 days before expiry via SMS</li>
                  <li className="flex gap-3"><span className="font-bold text-[#6366f1]">3.</span> Payment received via M-Pesa — PPPoE secret re-enabled instantly. Customer never loses service mid-month.</li>
                </ol>
              </div>

              <div className="mb-10">
                <h5 className="font-semibold mb-4 text-foreground/90">Key features</h5>
                <ul className="space-y-3 text-sm text-muted-foreground">
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-[#6366f1]" /> Monthly recurring billing via M-Pesa</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-[#6366f1]" /> PPPoE secret management (enable/disable on MikroTik)</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-[#6366f1]" /> Grace period — customer gets 24h before suspension</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-[#6366f1]" /> SMS dunning: T-3 days, T-1 day, and suspension notice</li>
                  <li className="flex items-center gap-3"><CheckCircle2 className="h-4 w-4 text-[#6366f1]" /> Auto-renewal with configurable billing cycle</li>
                </ul>
              </div>

              <Button className="w-full bg-[#6366f1] text-white hover:bg-[#6366f1]/90 h-12 rounded-full" render={<Link to="/signup?service=pppoe" />}>
                Set up fiber billing
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 5: HOW THE MAGIC COMMAND WORKS */}
      <section id="setup" className="py-24 bg-muted/20 px-4 md:px-6">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-16">
            <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">Setup in 60 seconds</h2>
            <h3 className="text-3xl md:text-4xl font-bold mb-6">Your MikroTik configures itself</h3>
            <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
              No SSH sessions. No Winbox navigation. No calling a technician. One command in the MikroTik terminal and ZealSync does the rest.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12 relative">
            {/* Horizontal connecting line on desktop */}
            <div className="hidden md:block absolute top-12 left-[16%] right-[16%] h-px bg-border/80 border-dashed border-t-2 border-border" />
            
            <div className="relative text-center md:text-left z-10 bg-muted/20 md:bg-transparent p-6 md:p-0 rounded-2xl md:rounded-none">
              <div className="w-16 h-16 mx-auto md:mx-0 bg-background border-2 border-primary/20 rounded-full flex items-center justify-center mb-6 shadow-sm">
                <Terminal className="h-8 w-8 text-primary" />
              </div>
              <h4 className="text-xl font-bold mb-3">Generate your setup command</h4>
              <p className="text-muted-foreground text-sm">Sign up, enter your router name, and ZealSync generates a unique one-line command just for your router.</p>
            </div>

            <div className="relative text-center md:text-left z-10 bg-muted/20 md:bg-transparent p-6 md:p-0 rounded-2xl md:rounded-none">
              <div className="w-16 h-16 mx-auto md:mx-0 bg-background border-2 border-primary/20 rounded-full flex items-center justify-center mb-6 shadow-sm">
                <Copy className="h-8 w-8 text-primary" />
              </div>
              <h4 className="text-xl font-bold mb-3">Paste it into your MikroTik terminal</h4>
              <p className="text-muted-foreground text-sm mb-4">Open Winbox Terminal, WebFig, or SSH. Paste the command. Press Enter. Walk away.</p>
              <div className="bg-[#0f172a] p-3 rounded-lg border border-border/20 text-left overflow-x-auto text-xs font-mono text-gray-300">
                /tool fetch url="https://api.zealsync.dev/api/v1/setup/TOKEN" \<br />
                &nbsp;&nbsp;dst-path=zealsync-setup.rsc mode=https; /import zealsync-setup.rsc
              </div>
            </div>

            <div className="relative text-center md:text-left z-10 bg-muted/20 md:bg-transparent p-6 md:p-0 rounded-2xl md:rounded-none">
              <div className="w-16 h-16 mx-auto md:mx-0 bg-background border-2 border-primary/20 rounded-full flex items-center justify-center mb-6 shadow-sm">
                <CheckCircle className="h-8 w-8 text-primary" />
              </div>
              <h4 className="text-xl font-bold mb-3">Dashboard updates automatically</h4>
              <p className="text-muted-foreground text-sm">ZealSync detects when your router is ready. No manual confirmation needed. Your dashboard shows the router as Online within 30 seconds.</p>
            </div>
          </div>
          
          <div className="text-center">
            <p className="text-xs text-muted-foreground/60 max-w-2xl mx-auto italic">
              The setup command configures WireGuard VPN, creates the API user, sets up speed profiles, and removes itself — all without storing credentials on the router.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 6: PLATFORM FEATURES GRID */}
      <section id="features" className="py-24 px-4 md:px-6">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">What's included</h2>
            <h3 className="text-3xl md:text-4xl font-bold">Everything your ISP needs in one platform</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
            {[
              { icon: Shield, title: "Duplicate payment protection", desc: "M-Pesa receipt unique constraint at database level. Daraja retry storms never double-credit a customer." },
              { icon: Wifi, title: "MikroTik RouterOS integration", desc: "Full REST API integration for hotspot users and PPPoE secrets. Works with CHR, physical RouterBOARDs, and CCRs." },
              { icon: RefreshCw, title: "Offline router recovery", desc: "Payment queued when your router blinks offline. Voucher activates automatically when connectivity restores." },
              { icon: Users, title: "Reseller self-service portal", desc: "Resellers top up a digital wallet via M-Pesa Paybill and generate vouchers 24/7 — no calls to you needed." },
              { icon: BarChart3, title: "Real-time admin dashboard", desc: "Revenue today, active sessions, vouchers, and router health — visible on your phone from anywhere." },
              { icon: MessageSquare, title: "SMS via Africa's Talking", desc: "Voucher codes, renewal reminders, and suspension notices delivered to your customers automatically." },
              { icon: Lock, title: "WireGuard VPN security", desc: "Your router's REST API is never exposed to the internet. All ZealSync traffic goes through an encrypted VPN tunnel." },
              { icon: Receipt, title: "KRA eTIMS compliant invoices", desc: "Every payment generates a tax-compliant invoice with a KRA QR code. Automatic compliance for registered businesses." }
            ].map((feat, idx) => (
              <div key={idx} className="bg-card border border-border p-6 rounded-2xl shadow-sm hover:border-primary/30 transition-colors flex flex-col items-start text-left">
                <div className="bg-primary/10 p-2.5 rounded-lg mb-4">
                  <feat.icon className="h-5 w-5 text-primary" />
                </div>
                <h4 className="font-bold mb-2 text-[15px]">{feat.title}</h4>
                <p className="text-muted-foreground text-sm leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* SECTION 7: DEMO / SCREENSHOT PLACEHOLDER */}
      <section id="demo" className="py-24 bg-muted/10 px-4 md:px-6 border-y border-border/40">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-12">
            <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">The dashboard</h2>
            <h3 className="text-3xl md:text-4xl font-bold">See your entire ISP business at a glance</h3>
          </div>

          <div className="rounded-xl border border-border/50 bg-[#0f1219] shadow-2xl overflow-hidden flex flex-col md:flex-row max-w-5xl mx-auto h-[500px]">
            {/* Sidebar */}
            <div className="hidden md:flex flex-col w-64 bg-[#0a0c12] border-r border-border/30 p-4">
              <div className="flex items-center gap-2 mb-10 mt-2 px-2">
                <Wifi className="h-5 w-5 text-primary" />
                <span className="font-bold text-white tracking-tight">ZealSync Admin</span>
              </div>
              <div className="space-y-1">
                {['Dashboard', 'Customers', 'Payments', 'Vouchers', 'Routers'].map((item, i) => (
                  <div key={i} className={`px-4 py-2.5 rounded-lg text-sm font-medium ${i === 0 ? 'bg-primary/20 text-primary' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
                    {item}
                  </div>
                ))}
              </div>
            </div>
            
            {/* Main Content area */}
            <div className="flex-1 p-6 md:p-8 overflow-hidden flex flex-col bg-[#0f1219]">
              <div className="flex justify-between items-center mb-8">
                <h4 className="text-xl font-semibold text-white">Overview</h4>
                <div className="text-xs text-gray-500 bg-gray-800/50 px-3 py-1 rounded-full border border-gray-700">Live data</div>
              </div>
              
              {/* Metric Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                {[
                  { label: "Revenue Today", val: "KES 4,500" },
                  { label: "Active Sessions", val: "142" },
                  { label: "Total Customers", val: "890" },
                  { label: "Active Vouchers", val: "356" }
                ].map((stat, i) => (
                  <div key={i} className="bg-[#171b26] border border-border/20 p-4 rounded-xl">
                    <div className="text-gray-400 text-xs font-medium mb-1">{stat.label}</div>
                    <div className="text-white font-bold text-xl">{stat.val}</div>
                  </div>
                ))}
              </div>

              {/* Table */}
              <div className="flex-1 bg-[#171b26] border border-border/20 rounded-xl overflow-hidden flex flex-col">
                <div className="px-5 py-4 border-b border-border/20 flex justify-between items-center">
                  <h5 className="text-sm font-semibold text-white">Recent Payments</h5>
                </div>
                <div className="flex-1 overflow-x-auto">
                  <table className="w-full text-sm text-left text-gray-300">
                    <thead className="text-xs text-gray-500 bg-[#0a0c12]/50">
                      <tr>
                        <th className="px-5 py-3 font-medium">Customer</th>
                        <th className="px-5 py-3 font-medium">Phone</th>
                        <th className="px-5 py-3 font-medium">Amount</th>
                        <th className="px-5 py-3 font-medium">Package</th>
                        <th className="px-5 py-3 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { name: "Mwangi J.", phone: "0712 345 678", amount: "KES 300", pkg: "Daily 10Mbps", status: "Confirmed", code: "green" },
                        { name: "Akinyi C.", phone: "0722 456 789", amount: "KES 1,500", pkg: "Monthly Fiber", status: "Confirmed", code: "green" },
                        { name: "Otieno P.", phone: "0733 567 890", amount: "KES 50", pkg: "Daily 10Mbps", status: "Pending", code: "yellow" },
                        { name: "Hassan A.", phone: "0700 678 901", amount: "KES 300", pkg: "Weekly 20Mbps", status: "Confirmed", code: "green" },
                        { name: "Wanjiku M.", phone: "0711 789 012", amount: "KES 1,500", pkg: "Monthly Fiber", status: "Confirmed", code: "green" }
                      ].map((row, i) => (
                        <tr key={i} className="border-b border-border/10 hover:bg-white/5">
                          <td className="px-5 py-3 text-white">{row.name}</td>
                          <td className="px-5 py-3 font-mono text-xs">{row.phone}</td>
                          <td className="px-5 py-3 font-medium">{row.amount}</td>
                          <td className="px-5 py-3">{row.pkg}</td>
                          <td className="px-5 py-3">
                            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${row.code === 'green' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
                              {row.code === 'green' ? '✅ Confirmed' : '🟡 Pending'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 8: PRICING */}
      <section id="pricing" className="py-24 px-4 md:px-6">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <h2 className="text-sm font-bold tracking-widest text-primary uppercase mb-2">Pricing</h2>
            <h3 className="text-3xl md:text-4xl font-bold mb-4">Simple flat-rate pricing. No percentage cuts.</h3>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Unlike other systems that take 3-5% of your hotspot revenue, ZealSync charges a flat monthly fee — so the more you earn, the more you keep.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            {/* Starter */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm flex flex-col">
              <h4 className="text-xl font-bold mb-2">Starter</h4>
              <div className="mb-6">
                <span className="text-3xl font-extrabold">KES 1,500</span>
                <span className="text-muted-foreground">/mo</span>
              </div>
              <ul className="space-y-3 mb-8 flex-1 text-sm text-muted-foreground">
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Up to 100 customers</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> 1 router</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Hotspot billing</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> M-Pesa STK Push</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Africa's Talking SMS (500 messages/mo)</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Admin dashboard</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> WhatsApp support</li>
              </ul>
              <Button variant="outline" className="w-full rounded-full" render={<Link to="/signup?tier=starter" />}>Start free trial</Button>
            </div>

            {/* Growth */}
            <div className="bg-card border-2 border-primary rounded-3xl p-6 shadow-xl flex flex-col relative scale-105 z-10">
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase">
                Most Popular
              </div>
              <h4 className="text-xl font-bold mb-2 text-primary">Growth</h4>
              <div className="mb-6">
                <span className="text-3xl font-extrabold">KES 2,500</span>
                <span className="text-muted-foreground">/mo</span>
              </div>
              <ul className="space-y-3 mb-8 flex-1 text-sm text-muted-foreground">
                <li className="flex gap-2 text-foreground font-medium"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Up to 300 customers</li>
                <li className="flex gap-2 text-foreground font-medium"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> 3 routers</li>
                <li className="flex gap-2 text-foreground font-medium"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Hotspot + PPPoE billing</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Everything in Starter</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Reseller portal + wallet</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> KRA eTIMS invoices</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Priority support</li>
              </ul>
              <Button className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary/90 shadow-md" render={<Link to="/signup?tier=growth" />}>Start free trial</Button>
            </div>

            {/* Scale */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm flex flex-col">
              <h4 className="text-xl font-bold mb-2">Scale</h4>
              <div className="mb-6">
                <span className="text-3xl font-extrabold">KES 4,000</span>
                <span className="text-muted-foreground">/mo</span>
              </div>
              <ul className="space-y-3 mb-8 flex-1 text-sm text-muted-foreground">
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Up to 700 customers</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> 10 routers</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Everything in Growth</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Multi-site management</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Analytics and revenue reports</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Dedicated onboarding call</li>
              </ul>
              <Button variant="outline" className="w-full rounded-full" render={<Link to="/signup?tier=scale" />}>Start free trial</Button>
            </div>

            {/* Enterprise */}
            <div className="bg-card border border-border rounded-3xl p-6 shadow-sm flex flex-col">
              <h4 className="text-xl font-bold mb-2">Enterprise</h4>
              <div className="mb-6">
                <span className="text-3xl font-extrabold">KES 6,000</span>
                <span className="text-muted-foreground">/mo</span>
              </div>
              <ul className="space-y-3 mb-8 flex-1 text-sm text-muted-foreground">
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Unlimited customers</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> 50 routers</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Everything in Scale</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> Custom SMS sender ID</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> API access</li>
                <li className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /> SLA guarantee</li>
              </ul>
              <Button variant="outline" className="w-full rounded-full" render={<Link to="/signup?tier=enterprise" />}>Start free trial</Button>
            </div>
          </div>

          <p className="text-center text-sm text-muted-foreground">
            All plans include a free 30-day pilot. No credit card required. Cancel anytime.
          </p>
        </div>
      </section>

      {/* SECTION 9: FOOTER CTA + FOOTER */}
      <section className="bg-card border-t border-border mt-auto">
        {/* Footer CTA */}
        <div className="bg-[#0a0c12] py-20 px-4 md:px-6 relative overflow-hidden border-b border-border/20">
          <div className="absolute inset-0 bg-primary/5" />
          <div className="container relative mx-auto max-w-4xl text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">Ready to stop managing billing manually?</h2>
            <p className="text-lg text-gray-400 mb-8 max-w-2xl mx-auto">
              Join Kenyan ISPs who automated their operations with ZealSync.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Button size="lg" className="w-full sm:w-auto h-12 px-8 text-base bg-primary text-primary-foreground hover:bg-primary/90 rounded-full" render={<Link to="/signup" />}>
                Start Free Trial
              </Button>
              <a href="https://wa.me/+254XXXXXXXXX" target="_blank" rel="noreferrer" className="text-primary hover:text-primary/80 font-medium text-sm transition-colors">
                Chat on WhatsApp
              </a>
            </div>
          </div>
        </div>

        {/* Main Footer */}
        <footer className="py-12 px-4 md:px-6 container mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-1 md:col-span-1">
              <Link to="/" className="flex items-center gap-2 mb-4">
                <Wifi className="h-6 w-6 text-primary" />
                <span className="text-xl font-bold tracking-tight text-foreground">ZealSync</span>
              </Link>
              <p className="text-sm text-muted-foreground">
                WiFi billing for Kenyan ISPs
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><button onClick={() => scrollToSection('hotspot')} className="hover:text-foreground transition-colors text-left">Hotspot Billing</button></li>
                <li><button onClick={() => scrollToSection('fiber')} className="hover:text-foreground transition-colors text-left">Fiber Billing</button></li>
                <li><button onClick={() => scrollToSection('pricing')} className="hover:text-foreground transition-colors text-left">Pricing</button></li>
                <li><button onClick={() => scrollToSection('features')} className="hover:text-foreground transition-colors text-left">Features</button></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-colors">Documentation</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Setup Guide</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">API Reference</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-colors">About</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Contact</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a></li>
              </ul>
            </div>
          </div>
          
          <div className="flex flex-col md:flex-row items-center justify-between pt-8 border-t border-border text-sm text-muted-foreground">
            <p>© 2026 Zeal Digital Solutions. Made in Nairobi, Kenya.</p>
            <div className="flex gap-4 mt-4 md:mt-0">
              <a href="#" className="hover:text-foreground transition-colors">GitHub</a>
              <a href="#" className="hover:text-foreground transition-colors">LinkedIn</a>
              <a href="#" className="hover:text-foreground transition-colors">Twitter</a>
            </div>
          </div>
        </footer>
      </section>
    </div>
  );
}
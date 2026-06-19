import { Link } from 'react-router-dom';
import { ArrowRight, Wifi, Zap, Smartphone, CheckCircle2, Shield, Globe } from 'lucide-react';
import { Button } from '../../components/ui/button';


export default function LandingPage() {
  return (
    <div className="flex flex-col">


      {/* Hero Section */}
      <section className="relative overflow-hidden bg-background pt-24 pb-32 lg:pt-36 lg:pb-40">
        {/* Abstract background blobs */}
        <div className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-80" aria-hidden="true">
          <div className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-primary to-chart-2 opacity-20 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }}></div>
        </div>

        <div className="container mx-auto px-4 md:px-6 flex flex-col items-center text-center">
          <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm font-medium text-primary mb-8 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4 duration-500">
            <Zap className="mr-1 h-4 w-4" /> Now available across major cities
          </div>
          
          <h1 className="max-w-4xl text-5xl font-extrabold tracking-tight sm:text-6xl md:text-7xl lg:text-8xl animate-in fade-in slide-in-from-bottom-6 duration-700">
            Grow Your ISP <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-primary to-chart-2 bg-clip-text text-transparent">
              With Zero Code.
            </span>
          </h1>
          
          <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl animate-in fade-in slide-in-from-bottom-8 duration-700 delay-150">
            ZealSync is the all-in-one billing and management platform for Kenyan WiFi Hotspot providers. Automate M-Pesa payments, manage routers, and grow your customer base.
          </p>
          
          <div className="mt-10 flex flex-col sm:flex-row items-center gap-4 animate-in fade-in slide-in-from-bottom-10 duration-700 delay-300">
            <Button size="lg" className="h-14 px-8 rounded-full text-base shadow-xl shadow-primary/25 transition-transform hover:-translate-y-1 bg-primary text-primary-foreground hover:bg-primary/90" render={<Link to="/signup" />}>
              Start Free Trial <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button size="lg" variant="outline" className="h-14 px-8 rounded-full text-base bg-background/50 backdrop-blur-sm" render={<a href="https://wa.me/254700000000" target="_blank" rel="noopener noreferrer" />}>
              Chat on WhatsApp
            </Button>
          </div>
          
          {/* Trust indicators */}
          <div className="mt-16 pt-8 border-t border-border/50 flex flex-col items-center animate-in fade-in duration-1000 delay-500">
            <p className="text-sm font-medium text-muted-foreground mb-4">Trusted by thousands of daily users</p>
            <div className="flex flex-wrap justify-center gap-8 opacity-50 grayscale">
              {/* Fake partner logos */}
              <div className="flex items-center gap-2 font-bold text-xl"><Globe className="h-6 w-6"/> FiberNet</div>
              <div className="flex items-center gap-2 font-bold text-xl"><Shield className="h-6 w-6"/> SecureLink</div>
              <div className="flex items-center gap-2 font-bold text-xl"><Wifi className="h-6 w-6"/> AirConnect</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-muted/30">
        <div className="container mx-auto px-4 md:px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">Built for ISP Founders</h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Everything you need to launch and scale your WiFi business, out of the box.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            {[
              {
                icon: Zap,
                title: 'Automated Provisioning',
                description: 'Instantly generate vouchers and connect users on MikroTik routers right after payment.',
              },
              {
                icon: Smartphone,
                title: 'M-Pesa Integration',
                description: 'C2B Paybill and STK Push out of the box. Zero manual reconciliation needed.',
              },
              {
                icon: Shield,
                title: 'Multi-Tenant SaaS',
                description: 'Secure, isolated environments for your business with role-based access for your team.',
              },
            ].map((feature, idx) => (
              <div key={idx} className="relative group rounded-3xl bg-background p-8 shadow-sm border transition-all hover:shadow-md hover:border-primary/30">
                <div className="absolute inset-0 rounded-3xl bg-gradient-to-b from-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
                <div className="relative">
                  <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <feature.icon className="h-6 w-6" />
                  </div>
                  <h3 className="mb-3 text-xl font-bold">{feature.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 bg-background">
        <div className="container mx-auto px-4 md:px-6">
          <div className="grid gap-16 lg:grid-cols-2 lg:gap-8 items-center">
            <div className="space-y-8">
              <div>
                <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Launch your ISP in minutes</h2>
                <p className="mt-4 text-lg text-muted-foreground">Skip the complex server setups and API integrations. We handle the heavy lifting so you can focus on sales.</p>
              </div>
              
              <div className="space-y-6">
                {[
                  { step: '01', title: 'Register your Business', desc: 'Sign up for a ZealSync tenant account.' },
                  { step: '02', title: 'Link your MikroTik', desc: 'Run our setup script on your router to establish a secure heartbeat.' },
                  { step: '03', title: 'Start Selling', desc: 'Create your packages and let customers connect via your branded portal.' },
                ].map((item, idx) => (
                  <div key={idx} className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold shadow-md">
                      {item.step}
                    </div>
                    <div>
                      <h4 className="text-xl font-semibold">{item.title}</h4>
                      <p className="mt-1 text-muted-foreground">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="relative mx-auto w-full max-w-md lg:max-w-none">
              <div className="aspect-[4/3] overflow-hidden rounded-3xl bg-muted border shadow-2xl relative flex items-center justify-center">
                {/* Decorative UI Mockup representation */}
                <div className="absolute inset-0 bg-gradient-to-br from-gray-100 to-gray-200" />
                <div className="relative w-3/4 h-3/4 bg-white rounded-xl shadow-lg border p-6 flex flex-col gap-4">
                  <div className="h-8 w-1/3 bg-gray-200 rounded-md" />
                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="h-24 bg-primary/10 border border-primary/20 rounded-lg" />
                    <div className="h-24 bg-gray-100 border rounded-lg" />
                  </div>
                  <div className="h-10 bg-primary/20 rounded-md mt-auto" />
                </div>
              </div>
              
              {/* Decorative blobs */}
              <div className="absolute -left-10 -bottom-10 h-40 w-40 rounded-full bg-chart-2 opacity-20 blur-2xl" />
              <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-primary opacity-20 blur-2xl" />
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section (Static) */}
      <section id="pricing" className="py-24 bg-muted/30">
        <div className="container mx-auto px-4 md:px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">Simple pricing for growing ISPs</h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Start for free, then upgrade as your customer base expands. Cancel anytime.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3 max-w-5xl mx-auto">
            {/* Bronze */}
            <div className="rounded-3xl bg-background border p-8 shadow-sm transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-semibold mb-2">Starter</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 1,500</span>
                <span className="text-muted-foreground font-medium"> / month</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['Up to 50 Customers', '1 MikroTik Router', 'Basic Branding', 'Email Support'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-full h-12" render={<Link to="/signup?tier=starter" />}>
                Start Free Trial
              </Button>
            </div>

            {/* Silver (Popular) */}
            <div className="relative rounded-3xl bg-background border-2 border-primary p-8 shadow-xl transition-transform hover:-translate-y-1 scale-105 z-10">
              <div className="absolute top-0 right-8 -translate-y-1/2 bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                Most Popular
              </div>
              <h3 className="text-xl font-semibold mb-2 text-primary">Pro</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 5,000</span>
                <span className="text-muted-foreground font-medium"> / month</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['Up to 500 Customers', '5 MikroTik Routers', 'Full Whitelabeling', 'Priority Support'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button className="w-full rounded-full h-12 shadow-lg shadow-primary/25 bg-primary text-primary-foreground hover:bg-primary/90" render={<Link to="/signup?tier=pro" />}>
                Start Free Trial
              </Button>
            </div>

            {/* Gold */}
            <div className="rounded-3xl bg-background border p-8 shadow-sm transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-semibold mb-2">Scale</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 15,000</span>
                <span className="text-muted-foreground font-medium"> / month</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['Unlimited Customers', 'Unlimited Routers', 'API Access', '24/7 Phone Support'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-full h-12" render={<Link to="/signup?tier=scale" />}>
                Start Free Trial
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-primary" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMCIgaGVpZ2h0PSIyMCI+PHBhdGggZD0iTTAgMGgyMHYyMEgwem0xMCAxMGgxMHYxMEgxMHoiIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4wNSIvPjwvc3ZnPg==')] opacity-30 mix-blend-overlay" />
        
        <div className="container relative z-10 mx-auto px-4 md:px-6 text-center text-primary-foreground">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl mb-6">Ready to scale your WiFi business?</h2>
          <p className="text-primary-foreground/80 text-lg mb-10 max-w-2xl mx-auto">
            Join hundreds of ISPs who have already made the switch. Create your tenant account today and go live in minutes.
          </p>
          <Button size="lg" className="h-14 px-10 rounded-full text-lg font-bold bg-background text-primary hover:bg-background/90 shadow-xl transition-transform hover:scale-105" render={<Link to="/signup" />}>
            Create Free Account
          </Button>
        </div>
      </section>


    </div>
  );
}
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
          <div className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-primary to-[#9089fc] opacity-20 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]" style={{ clipPath: 'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)' }}></div>
        </div>

        <div className="container mx-auto px-4 md:px-6 flex flex-col items-center text-center">
          <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm font-medium text-primary mb-8 backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4 duration-500">
            <Zap className="mr-1 h-4 w-4" /> Now available across major cities
          </div>
          
          <h1 className="max-w-4xl text-5xl font-extrabold tracking-tight sm:text-6xl md:text-7xl lg:text-8xl animate-in fade-in slide-in-from-bottom-6 duration-700">
            Fast, Reliable WiFi <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-primary to-blue-600 bg-clip-text text-transparent">
              On Your Terms.
            </span>
          </h1>
          
          <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl animate-in fade-in slide-in-from-bottom-8 duration-700 delay-150">
            Experience ultra-fast internet with instant M-Pesa payments. No contracts, no hidden fees, just seamless connectivity when you need it.
          </p>
          
          <div className="mt-10 flex flex-col sm:flex-row items-center gap-4 animate-in fade-in slide-in-from-bottom-10 duration-700 delay-300">
            <Button size="lg" className="h-14 px-8 rounded-full text-base shadow-xl shadow-primary/25 transition-transform hover:-translate-y-1" render={<Link to="/register" />} nativeButton={false}>
                Get Connected Now <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button size="lg" variant="outline" className="h-14 px-8 rounded-full text-base bg-background/50 backdrop-blur-sm" render={<a href="#pricing" />} nativeButton={false}>
              View Packages
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
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">Everything you need, nothing you don't</h2>
            <p className="mt-4 text-lg text-muted-foreground">
              We've built our network from the ground up to provide the most frictionless internet experience possible.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3">
            {[
              {
                icon: Zap,
                title: 'Blazing Fast Speeds',
                description: 'Enjoy buffer-free streaming, smooth video calls, and lightning-fast downloads on our modern network infrastructure.',
              },
              {
                icon: Smartphone,
                title: 'Instant M-Pesa Payments',
                description: 'No waiting in lines or dealing with complex billing. Pay via M-Pesa STK push and get connected in seconds.',
              },
              {
                icon: Shield,
                title: 'No Long-Term Contracts',
                description: 'Pay only for what you use. Choose from daily, weekly, or monthly packages with zero cancellation fees.',
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
                <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Get online in three simple steps</h2>
                <p className="mt-4 text-lg text-muted-foreground">Our seamless onboarding process means you can go from offline to blazing fast internet in under two minutes.</p>
              </div>
              
              <div className="space-y-6">
                {[
                  { step: '01', title: 'Create an Account', desc: 'Sign up with just your email and M-Pesa phone number.' },
                  { step: '02', title: 'Select a Package', desc: 'Choose a data plan that fits your current needs.' },
                  { step: '03', title: 'Enter M-Pesa PIN', desc: 'Approve the prompt on your phone and instantly receive your voucher code.' },
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
              <div className="absolute -left-10 -bottom-10 h-40 w-40 rounded-full bg-blue-400 opacity-20 blur-2xl" />
              <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-primary opacity-20 blur-2xl" />
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section (Static) */}
      <section id="pricing" className="py-24 bg-muted/30">
        <div className="container mx-auto px-4 md:px-6">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">Simple, transparent pricing</h2>
            <p className="mt-4 text-lg text-muted-foreground">
              No hidden fees, no surprise charges. Pay for exactly what you need.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3 max-w-5xl mx-auto">
            {/* Bronze */}
            <div className="rounded-3xl bg-background border p-8 shadow-sm transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-semibold mb-2">Daily Bronze</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 50</span>
                <span className="text-muted-foreground font-medium"> / day</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['10 Mbps Speeds', 'Unlimited Data', '1 Device', '24h Access'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-full h-12" render={<Link to="/register" />} nativeButton={false}>
                Get Started
              </Button>
            </div>

            {/* Silver (Popular) */}
            <div className="relative rounded-3xl bg-background border-2 border-primary p-8 shadow-xl transition-transform hover:-translate-y-1 scale-105 z-10">
              <div className="absolute top-0 right-8 -translate-y-1/2 bg-primary text-primary-foreground px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                Most Popular
              </div>
              <h3 className="text-xl font-semibold mb-2 text-primary">Weekly Silver</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 300</span>
                <span className="text-muted-foreground font-medium"> / week</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['20 Mbps Speeds', 'Unlimited Data', '2 Devices', '7 Days Access'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button className="w-full rounded-full h-12 shadow-lg shadow-primary/25" render={<Link to="/register" />} nativeButton={false}>
                Get Started
              </Button>
            </div>

            {/* Gold */}
            <div className="rounded-3xl bg-background border p-8 shadow-sm transition-transform hover:-translate-y-1">
              <h3 className="text-xl font-semibold mb-2">Monthly Gold</h3>
              <div className="mb-6">
                <span className="text-4xl font-extrabold">Ksh 1,000</span>
                <span className="text-muted-foreground font-medium"> / month</span>
              </div>
              <ul className="mb-8 space-y-4">
                {['50 Mbps Speeds', 'Unlimited Data', '5 Devices', '30 Days Access'].map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                    <span className="text-muted-foreground">{feature}</span>
                  </li>
                ))}
              </ul>
              <Button variant="outline" className="w-full rounded-full h-12" render={<Link to="/register" />} nativeButton={false}>
                Get Started
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
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl mb-6">Ready to experience better WiFi?</h2>
          <p className="text-primary-foreground/80 text-lg mb-10 max-w-2xl mx-auto">
            Join thousands of users who have already made the switch. Create your account today and get connected in seconds.
          </p>
          <Button size="lg" variant="secondary" className="h-14 px-10 rounded-full text-lg font-bold text-primary hover:bg-white shadow-xl transition-transform hover:scale-105" render={<Link to="/register" />} nativeButton={false}>
            Create Free Account
          </Button>
        </div>
      </section>


    </div>
  );
}
import { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Wifi, Menu, X } from 'lucide-react';
import { Button } from '../ui/button';

export default function PublicLayout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();
  const isLandingPage = location.pathname === '/';

  return (
    <div className="flex min-h-screen flex-col font-sans selection:bg-primary/20 bg-background">
      {/* Premium Navigation */}
      <nav className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center justify-between px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2" onClick={() => setIsMobileMenuOpen(false)}>
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Wifi className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold tracking-tight">ZealSync</span>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden md:flex md:items-center md:gap-6 lg:gap-8">
            <a href={isLandingPage ? "#features" : "/#features"} className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">Features</a>
            <a href={isLandingPage ? "#pricing" : "/#pricing"} className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground">Pricing</a>
            <div className="flex items-center gap-4">
              <Button variant="ghost" render={<Link to="/login" />} nativeButton={false}>
                Log in
              </Button>
              <Button className="rounded-full shadow-lg shadow-primary/20 bg-primary text-primary-foreground hover:bg-primary/90" render={<Link to="/register" />} nativeButton={false}>
                Get Connected
              </Button>
            </div>
          </div>

          {/* Mobile Menu Toggle */}
          <Button 
            variant="ghost" 
            size="icon" 
            className="md:hidden" 
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {/* Mobile Nav */}
        {isMobileMenuOpen && (
          <div className="container mx-auto p-4 md:hidden border-t bg-background animate-in slide-in-from-top-2">
            <div className="flex flex-col space-y-4">
              <a 
                href={isLandingPage ? "#features" : "/#features"}
                className="text-sm font-medium p-2 hover:bg-muted rounded-md"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Features
              </a>
              <a 
                href={isLandingPage ? "#pricing" : "/#pricing"}
                className="text-sm font-medium p-2 hover:bg-muted rounded-md"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                Pricing
              </a>
              <div className="flex flex-col gap-2 pt-2 border-t">
                <Button variant="outline" className="w-full justify-center" render={<Link to="/login" />} nativeButton={false} onClick={() => setIsMobileMenuOpen(false)}>
                  Log in
                </Button>
                <Button className="w-full justify-center bg-primary text-primary-foreground hover:bg-primary/90" render={<Link to="/register" />} nativeButton={false} onClick={() => setIsMobileMenuOpen(false)}>
                  Get Connected
                </Button>
              </div>
            </div>
          </div>
        )}
      </nav>

      <main className="flex-1">
        <Outlet />
      </main>

      {/* Premium Footer */}
      <footer className="bg-background py-12 border-t">
        <div className="container mx-auto px-4 md:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
                  <Wifi className="h-5 w-5 text-primary-foreground" />
                </div>
                <span className="text-xl font-bold tracking-tight">ZealSync</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Next-generation WiFi billing and hotspot management for the modern world.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href={isLandingPage ? "#features" : "/#features"} className="hover:text-foreground transition-colors">Features</a></li>
                <li><a href={isLandingPage ? "#pricing" : "/#pricing"} className="hover:text-foreground transition-colors">Pricing</a></li>
                <li><Link to="/register" className="hover:text-foreground transition-colors">Reseller Program</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Support</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-colors">Help Center</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Contact Us</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Status</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-foreground transition-colors">Refund Policy</a></li>
              </ul>
            </div>
          </div>
          
          <div className="flex flex-col md:flex-row items-center justify-between pt-8 border-t border-border/50 text-sm text-muted-foreground">
            <p>© {new Date().getFullYear()} ZealSync Networks. All rights reserved.</p>
            <div className="flex gap-4 mt-4 md:mt-0">
              <span>Made with ❤️ in Nairobi</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
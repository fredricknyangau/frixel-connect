import { Link, Outlet } from 'react-router-dom';
import { Button } from '../ui/button';

export default function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col font-sans">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-xl font-bold text-primary">ZealSync</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Button variant="ghost" render={<Link to="/login" />} className="hidden sm:inline-flex" nativeButton={false}>
              Login
            </Button>
            <Button render={<Link to="/register" />} nativeButton={false}>
              Get Started
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t bg-muted/40 py-8">
        <div className="container mx-auto flex flex-col items-center justify-between gap-4 px-4 sm:flex-row text-center sm:text-left">
          <p className="text-sm text-muted-foreground">
            © {new Date().getFullYear()} ZealSync. All rights reserved.
          </p>
          <nav className="flex items-center gap-4 text-sm text-muted-foreground">
            <Link to="#" className="hover:text-foreground">Privacy</Link>
            <Link to="#" className="hover:text-foreground">Terms</Link>
            <Link to="#" className="hover:text-foreground">Contact</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
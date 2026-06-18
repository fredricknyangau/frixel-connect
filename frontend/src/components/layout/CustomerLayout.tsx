import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { 
  Home, 
  Wifi, 
  Ticket, 
  UserCircle,
  LogOut,
  Receipt
} from 'lucide-react';
import { useAuthContext } from '../../context/AuthContext';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';

interface NavItem {
  icon: typeof Home;
  label: string;
  href: string;
}

const navItems: NavItem[] = [
  { icon: Home, label: 'Home', href: '/customer/dashboard' },
  { icon: Wifi, label: 'Buy WiFi', href: '/customer/buy' },
  { icon: Ticket, label: 'Vouchers', href: '/customer/vouchers' },
  { icon: Receipt, label: 'Invoices', href: '/customer/invoices' },
  { icon: UserCircle, label: 'Profile', href: '/customer/profile' },
];

export default function CustomerLayout() {
  const { logout } = useAuthContext();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen flex-col bg-muted/20 pb-16 md:pb-0">
      {/* Top Header - Mobile and Desktop */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b bg-background px-4">
        <span className="text-lg font-bold">ZealSync</span>
        <Button variant="ghost" size="sm" onClick={handleLogout} className="md:hidden">
          <LogOut className="h-4 w-4 mr-2" />
          Logout
        </Button>
        {/* Desktop Navigation (hidden on mobile) */}
        <nav className="hidden md:flex items-center gap-6 mr-4">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 text-sm font-medium transition-colors hover:text-primary',
                  isActive ? 'text-primary' : 'text-muted-foreground'
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 p-4 md:p-8 max-w-4xl mx-auto w-full">
        <Outlet />
      </main>

      {/* Bottom Navigation - Mobile Only */}
      <nav className="fixed bottom-0 z-40 w-full border-t bg-background md:hidden safe-area-bottom">
        <div className="flex h-16 items-center justify-around px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex flex-col items-center justify-center gap-1 min-w-[64px] h-full transition-colors',
                  isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                )
              }
            >
              <item.icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
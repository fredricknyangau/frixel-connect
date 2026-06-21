import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { 
  LayoutDashboard, 
  Building2, 
  ScrollText, 
  Users,
  LogOut,
  Menu,
  Moon,
  Sun,
  ShieldCheck
} from 'lucide-react';
import { useSuperAdminAuth } from '../../context/SuperAdminAuthContext';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '../ui/sheet';
import { Badge } from '../ui/badge';
import { useTheme } from '@/hooks/useTheme';

interface SidebarItem {
  icon: typeof LayoutDashboard;
  label: string;
  href: string;
}

const sidebarItems: SidebarItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/super-admin/dashboard' },
  { icon: Building2, label: 'Tenants', href: '/super-admin/tenants' },
  { icon: ScrollText, label: 'Audit Log', href: '/super-admin/audit-log' },
  { icon: Users, label: 'SA Accounts', href: '/super-admin/accounts' },
];

export default function SuperAdminLayout() {
  const { logout, superAdmin } = useSuperAdminAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/super-admin/login');
  };

  const NavItems = ({ isMobile = false }: { isMobile?: boolean }) => {
    const { theme, setTheme } = useTheme();

    return (
      <nav className={cn('flex flex-col gap-2 flex-1', isMobile ? 'mt-4' : 'mt-8')}>
        <div className="flex-1 flex flex-col gap-2">
          {sidebarItems.map((item) => (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-red-650 text-white shadow-md shadow-red-950/40 border-l-4 border-red-500 bg-red-950/30'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                )
              }
            >
              <item.icon className="h-4.5 w-4.5" />
              {item.label}
            </NavLink>
          ))}
        </div>
        
        <div className="mt-auto flex flex-col gap-3 pt-4 border-t border-slate-800/80">
          <div className="px-3 py-2 rounded-lg bg-slate-950/40 border border-slate-800/50">
            <p className="text-xs font-semibold text-slate-300 truncate">{superAdmin?.full_name}</p>
            <p className="text-[10px] text-slate-500 truncate mt-0.5">ZealSync Operator</p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="flex-1 justify-start gap-2 px-3 text-slate-400 hover:bg-slate-800 hover:text-white"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              <span className="text-xs">{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
            </Button>
          </div>

          <Button 
            variant="ghost" 
            className="w-full justify-start gap-3 text-slate-400 hover:bg-red-950/20 hover:text-red-400 transition-colors px-3"
            onClick={handleLogout}
          >
            <LogOut className="h-4.5 w-4.5" />
            <span className="text-xs font-semibold">Sign Out</span>
          </Button>
        </div>
      </nav>
    );
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Dynamic page title fallback for safety */}
      <Helmet>
        <title>⚠ SUPER ADMIN | ZealSync</title>
      </Helmet>

      {/* Desktop Sidebar (Red-tinted dark background: oklch(0.13 0.03 15) equivalent) */}
      <aside className="hidden w-64 flex-col border-r border-slate-800/60 bg-[oklch(0.13_0.03_15)] px-4 py-6 md:flex fixed inset-y-0 z-50">
        <div className="flex items-center justify-between px-2">
          <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-red-400 to-amber-500 bg-clip-text text-transparent flex items-center">
            ZealSync<sup className="text-[10px] text-red-500 font-bold ml-1 font-mono tracking-normal">SA</sup>
          </span>
          <Badge className="bg-red-950/40 text-red-400 border border-red-900/30 text-[10px] px-1.5 py-0">
            Control
          </Badge>
        </div>
        <NavItems />
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col md:pl-64">
        {/* Top Control Panel Header Bar */}
        <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-slate-800/60 bg-slate-900/40 backdrop-blur-md px-6">
          <div className="hidden md:flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-red-500" />
            <span className="text-[10px] uppercase font-mono tracking-widest font-bold text-slate-500">
              ZealSync Control Panel
            </span>
          </div>

          {/* Mobile Header Branding */}
          <div className="flex md:hidden items-center gap-2">
            <span className="text-lg font-bold bg-gradient-to-r from-red-400 to-amber-500 bg-clip-text text-transparent">
              ZealSync<sup className="text-[9px] text-red-500 font-bold ml-0.5">SA</sup>
            </span>
            <Badge className="bg-red-950/40 text-red-400 border border-red-900/30 text-[8px] px-1 py-0">
              Control
            </Badge>
          </div>
          
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="text-slate-300 hover:bg-slate-800 md:hidden" />}>
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle navigation menu</span>
            </SheetTrigger>
            <SheetContent side="right" className="w-64 bg-[oklch(0.13_0.03_15)] border-slate-800 text-slate-100 p-5">
              <SheetTitle className="sr-only">Control Panel Menu</SheetTitle>
              <div className="flex items-center gap-2 pb-4 border-b border-slate-800">
                <span className="text-lg font-bold bg-gradient-to-r from-red-400 to-amber-500 bg-clip-text text-transparent">
                  ZealSync<sup className="text-[9px] text-red-500 font-bold ml-0.5">SA</sup>
                </span>
              </div>
              <NavItems isMobile />
            </SheetContent>
          </Sheet>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 md:p-8 bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

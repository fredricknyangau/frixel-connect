import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Building2, 
  ScrollText, 
  ShieldAlert,
  LogOut,
  Menu,
  Moon,
  Sun
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
  { icon: ShieldAlert, label: 'Super Admins', href: '/super-admin/accounts' },
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
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-teal-600 text-white shadow-md shadow-teal-900/20'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                )
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </div>
        
        <div className="mt-auto flex flex-col gap-2 pt-4 border-t border-slate-800">
          <div className="px-3 py-2 text-xs text-slate-500">
            Logged in as <span className="font-semibold text-slate-300">{superAdmin?.full_name}</span>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="w-full justify-start gap-2 px-2 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            {theme === 'dark'
              ? <Sun className="w-4 h-4" />
              : <Moon className="w-4 h-4" />
            }
            <span className="text-sm">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          </Button>

          <Button 
            variant="ghost" 
            className="w-full justify-start gap-3 text-slate-400 hover:bg-slate-800 hover:text-white hover:text-red-400"
            onClick={handleLogout}
          >
            <LogOut className="h-5 w-5" />
            Logout
          </Button>
        </div>
      </nav>
    );
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 flex-col border-r border-slate-800 bg-slate-900 px-4 py-6 md:flex fixed inset-y-0 z-50">
        <div className="flex items-center justify-between px-2">
          <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
            ZealSync
          </span>
          <Badge className="bg-teal-950 text-teal-400 hover:bg-teal-900 border border-teal-800">
            Super Admin
          </Badge>
        </div>
        <NavItems />
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col md:pl-64">
        {/* Mobile Header */}
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 md:hidden">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold bg-gradient-to-r from-indigo-400 to-teal-400 bg-clip-text text-transparent">
              ZealSync
            </span>
            <Badge className="bg-teal-950 text-teal-400 hover:bg-teal-900 border border-teal-800 text-[10px] px-1.5 py-0">
              Super Admin
            </Badge>
          </div>
          
          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="text-slate-300 hover:bg-slate-800 md:hidden" />}>
              <Menu className="h-6 w-6" />
              <span className="sr-only">Toggle navigation menu</span>
            </SheetTrigger>
            <SheetContent side="right" className="w-64 bg-slate-900 border-slate-800 text-slate-100">
              <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
              <NavItems isMobile />
            </SheetContent>
          </Sheet>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 md:p-8 bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

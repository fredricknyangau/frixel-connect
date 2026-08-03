import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Package,
  CreditCard,
  Ticket,
  Activity,
  LogOut,
  Menu,
  Wifi,
  Repeat,
  Receipt,
  ScrollText,
  Building2,
  Moon,
  Sun,
} from 'lucide-react';
import { useAuthContext } from '../../context/AuthContext';
import { useRouterSummary } from '../../hooks/useRouterSummary';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '../ui/sheet';
import { Badge } from '../ui/badge';
import { useTheme } from '@/hooks/useTheme';

interface SidebarItem {
  icon: typeof LayoutDashboard;
  label: string;
  href: string;
  navState?: 'active' | 'muted' | 'disabled';
}

const coreSidebarItems: SidebarItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/admin/dashboard' },
  { icon: Users, label: 'Customers', href: '/admin/customers' },
  { icon: Package, label: 'Packages', href: '/admin/packages' },
  { icon: CreditCard, label: 'Payments', href: '/admin/payments' },
  { icon: Receipt, label: 'Invoices', href: '/admin/invoices' },
  { icon: Activity, label: 'Sessions', href: '/admin/sessions' },
  { icon: Wifi, label: 'Routers', href: '/admin/routers' },
  { icon: Activity, label: 'System Health', href: '/admin/system-health' },
  { icon: ScrollText, label: 'Audit Log', href: '/admin/audit-log' },
  { icon: Building2, label: 'Account & Billing', href: '/admin/account' },
];

export default function AdminLayout() {
  const { logout } = useAuthContext();
  const navigate = useNavigate();
  const { hasHotspotRouter, hasPPPoERouter, routers } = useRouterSummary();

  const hasAnyRouter = routers.length > 0;

  /** Vouchers: enabled when hotspot router exists; muted when no routers yet; hidden-style when fiber-only. */
  const vouchersNavState: 'active' | 'muted' | 'disabled' = !hasAnyRouter
    ? 'muted'
    : hasHotspotRouter
      ? 'active'
      : 'disabled';

  /** Subscriptions: enabled when PPPoE router exists; muted when no routers; disabled when hotspot-only. */
  const subscriptionsNavState: 'active' | 'muted' | 'disabled' = !hasAnyRouter
    ? 'muted'
    : hasPPPoERouter
      ? 'active'
      : 'disabled';

  const serviceSidebarItems: SidebarItem[] = [
    { icon: Ticket, label: 'Vouchers', href: '/admin/vouchers', navState: vouchersNavState },
    { icon: Repeat, label: 'Subscriptions', href: '/admin/subscriptions', navState: subscriptionsNavState },
  ];

  const sidebarItems: SidebarItem[] = [
    ...coreSidebarItems.slice(0, 5),
    ...serviceSidebarItems,
    ...coreSidebarItems.slice(5),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const NavItems = ({ isMobile = false }: { isMobile?: boolean }) => {
    const { theme, setTheme } = useTheme();

    return (
      <nav className={cn('flex flex-col gap-2 flex-1', isMobile ? 'mt-4' : 'mt-8')}>
        <div className="flex-1 flex flex-col gap-2">
          {sidebarItems.map((item) => {
            const navState = item.navState ?? 'active';

            if (navState === 'disabled') {
              return (
                <span
                  key={item.href}
                  className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground/50"
                  title="Connect a router with this service type first"
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </span>
              );
            }

            return (
              <NavLink
                key={item.href}
                to={item.href}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    navState === 'muted' && 'opacity-50',
                  )
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            );
          })}
        </div>

        <div className="mt-auto flex flex-col gap-2 border-t pt-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="w-full justify-start gap-2 px-2"
          >
            {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            <span className="text-sm">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
          </Button>

          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground"
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
    <div className="flex min-h-screen bg-muted/20">
      <aside className="fixed inset-y-0 z-50 hidden w-64 flex-col border-r bg-background px-4 py-6 md:flex">
        <div className="flex items-center justify-between px-2">
          <span className="text-xl font-bold">Frixel Connect</span>
          <Badge variant="secondary">Admin</Badge>
        </div>
        <NavItems />
      </aside>

      <div className="flex flex-1 flex-col md:pl-64">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b bg-background px-4 md:hidden">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">Frixel Connect</span>
            <Badge variant="secondary">Admin</Badge>
          </div>

          <Sheet>
            <SheetTrigger render={<Button variant="ghost" size="icon" className="md:hidden" />}>
              <Menu className="h-6 w-6" />
              <span className="sr-only">Toggle navigation menu</span>
            </SheetTrigger>
            <SheetContent side="right" className="w-64">
              <SheetTitle className="sr-only">Navigation Menu</SheetTitle>
              <NavItems isMobile />
            </SheetContent>
          </Sheet>
        </header>

        <main className="flex-1 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

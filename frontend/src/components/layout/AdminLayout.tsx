import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Package, 
  CreditCard, 
  Ticket, 
  Activity,
  LogOut,
  Menu
} from 'lucide-react';
import { useAuthContext } from '../../context/AuthContext';
import { cn } from '../../lib/utils';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from '../ui/sheet';
import { Badge } from '../ui/badge';

interface SidebarItem {
  icon: typeof LayoutDashboard;
  label: string;
  href: string;
}

const sidebarItems: SidebarItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/admin/dashboard' },
  { icon: Users, label: 'Customers', href: '/admin/customers' },
  { icon: Package, label: 'Packages', href: '/admin/packages' },
  { icon: CreditCard, label: 'Payments', href: '/admin/payments' },
  { icon: Ticket, label: 'Vouchers', href: '/admin/vouchers' },
  { icon: Activity, label: 'Sessions', href: '/admin/sessions' },
];

export default function AdminLayout() {
  const { logout } = useAuthContext();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const NavItems = ({ isMobile = false }: { isMobile?: boolean }) => (
    <nav className={cn('flex flex-col gap-2', isMobile ? 'mt-4' : 'mt-8')}>
      {sidebarItems.map((item) => (
        <NavLink
          key={item.href}
          to={item.href}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )
          }
        >
          <item.icon className="h-5 w-5" />
          {item.label}
        </NavLink>
      ))}
      <Button 
        variant="ghost" 
        className="mt-auto flex justify-start gap-3 text-muted-foreground hover:text-foreground md:mt-8"
        onClick={handleLogout}
      >
        <LogOut className="h-5 w-5" />
        Logout
      </Button>
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-muted/20">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 flex-col border-r bg-background px-4 py-6 md:flex fixed inset-y-0 z-50">
        <div className="flex items-center justify-between px-2">
          <span className="text-xl font-bold">ZealSync</span>
          <Badge variant="secondary">Admin</Badge>
        </div>
        <NavItems />
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col md:pl-64">
        {/* Mobile Header */}
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b bg-background px-4 md:hidden">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold">ZealSync</span>
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

        {/* Page Content */}
        <main className="flex-1 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
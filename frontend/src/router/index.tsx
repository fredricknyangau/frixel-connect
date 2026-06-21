import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Suspense, lazy } from 'react';

import ProtectedRoute from '../components/shared/ProtectedRoute';
import PublicLayout from '../components/layout/PublicLayout';
import AdminLayout from '../components/layout/AdminLayout';
import ResellerLayout from '../components/layout/ResellerLayout';
import CustomerLayout from '../components/layout/CustomerLayout';
import SuperAdminLayout from '../components/layout/SuperAdminLayout';
import SuperAdminRoute from '../components/shared/SuperAdminRoute';
import { SuperAdminAuthProvider } from '../context/SuperAdminAuthContext';
import { LoadingSpinner } from '../components/shared/LoadingSpinner';

import LandingPage from '../pages/public/LandingPage';
import LoginPage from '../pages/public/LoginPage';
import RegisterPage from '../pages/public/RegisterPage';
import TenantSignupPage from '../pages/public/TenantSignupPage';
import CaptivePortalPage from '../pages/public/CaptivePortalPage';

import OnboardingWizard from '../pages/admin/onboarding/OnboardingWizard';
import RouterOnboardingWizard from '../pages/admin/onboarding/RouterOnboardingWizard';
import AdminDashboard from '../pages/admin/DashboardPage';
import AdminCustomers from '../pages/admin/CustomersPage';
import AdminPackages from '../pages/admin/PackagesPage';
import AdminPayments from '../pages/admin/PaymentsPage';
import AdminVouchers from '../pages/admin/VouchersPage';
import AdminSessions from '../pages/admin/SessionsPage';
import AdminRouters from '../pages/admin/RoutersPage';
import AdminSubscriptions from '../pages/admin/SubscriptionsPage';
import AdminInvoices from '../pages/admin/InvoicesPage';
import AdminSystemHealth from '../pages/admin/SystemHealthPage';
import AdminAuditLog from '../pages/admin/AuditLogPage';
import AdminAccount from '../pages/admin/AccountPage';

import ResellerDashboard from '../pages/reseller/ResellerDashboard';
import ResellerCustomers from '../pages/reseller/MyCustomersPage';
import ResellerPayments from '../pages/reseller/ResellerPaymentsPage';
import ResellerVouchers from '../pages/reseller/ResellerVouchersPage';
import ResellerWallet from '../pages/reseller/WalletPage';

import CustomerDashboard from '../pages/customer/DashboardPage';
import CustomerBuyPackage from '../pages/customer/BuyPackagePage';
import CustomerPaymentStatus from '../pages/customer/PaymentStatusPage';
import CustomerVouchers from '../pages/customer/VouchersPage';
import CustomerInvoices from '../pages/customer/InvoicesPage';
import CustomerProfile from '../pages/customer/ProfilePage';
import CustomerDataPrivacy from '../pages/customer/DataPrivacyPage';

// Lazy load all super admin pages for separation of concerns and bundle size optimization
const SuperAdminLoginPage = lazy(() => import('../pages/super-admin/SuperAdminLoginPage'));
const SuperAdminDashboardPage = lazy(() => import('../pages/super-admin/DashboardPage'));
const TenantsPage = lazy(() => import('../pages/super-admin/TenantsPage'));
const TenantDetailPage = lazy(() => import('../pages/super-admin/TenantDetailPage'));
const AuditLogPage = lazy(() => import('../pages/super-admin/AuditLogPage'));
const AccountsPage = lazy(() => import('../pages/super-admin/AccountsPage'));

// Helper to wrap lazy-loaded components with Suspense and a full-page loading indicator
const lazyLoad = (Component: React.ComponentType<any>) => (
  <Suspense fallback={<LoadingSpinner fullPage />}>
    <Component />
  </Suspense>
);

// Inline fallback 404 page
const NotFound = () => (
  <div className="flex h-screen flex-col items-center justify-center space-y-4">
    <h1 className="text-4xl font-bold">404</h1>
    <p className="text-gray-600">Page not found</p>
    <a href="/" className="text-blue-500 hover:underline">Return Home</a>
  </div>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'signup', element: <TenantSignupPage /> },
      { path: 'hotspot/login', element: <CaptivePortalPage /> },
    ],
  },
  {
    path: '/admin',
    element: <ProtectedRoute allowedRoles={['admin']} />,
    children: [
      { path: 'onboarding', element: <OnboardingWizard /> },
      { path: 'onboarding/router', element: <RouterOnboardingWizard /> },
      {
        element: <AdminLayout />,
        children: [
          { index: true, element: <Navigate to="/admin/dashboard" replace /> },
          { path: 'dashboard', element: <AdminDashboard /> },
          { path: 'customers', element: <AdminCustomers /> },
          { path: 'packages', element: <AdminPackages /> },
          { path: 'payments', element: <AdminPayments /> },
          { path: 'vouchers', element: <AdminVouchers /> },
          { path: 'sessions', element: <AdminSessions /> },
          { path: 'routers', element: <AdminRouters /> },
          { path: 'subscriptions', element: <AdminSubscriptions /> },
          { path: 'invoices', element: <AdminInvoices /> },
          { path: 'system-health', element: <AdminSystemHealth /> },
          { path: 'audit-log', element: <AdminAuditLog /> },
          { path: 'account', element: <AdminAccount /> },
        ]
      }
    ]
  },
  {
    path: '/reseller',
    element: <ProtectedRoute allowedRoles={['reseller']} />,
    children: [
      {
        element: <ResellerLayout />,
        children: [
          { index: true, element: <Navigate to="/reseller/dashboard" replace /> },
          { path: 'dashboard', element: <ResellerDashboard /> },
          { path: 'customers', element: <ResellerCustomers /> },
          { path: 'payments', element: <ResellerPayments /> },
          { path: 'vouchers', element: <ResellerVouchers /> },
          { path: 'wallet', element: <ResellerWallet /> },
        ]
      }
    ]
  },
  {
    path: '/customer',
    element: <ProtectedRoute allowedRoles={['customer']} />,
    children: [
      {
        element: <CustomerLayout />,
        children: [
          { index: true, element: <Navigate to="/customer/dashboard" replace /> },
          { path: 'dashboard', element: <CustomerDashboard /> },
          { path: 'buy', element: <CustomerBuyPackage /> },
          { path: 'status/:id', element: <CustomerPaymentStatus /> },
          { path: 'vouchers', element: <CustomerVouchers /> },
          { path: 'invoices', element: <CustomerInvoices /> },
          { path: 'profile', element: <CustomerProfile /> },
          { path: 'privacy', element: <CustomerDataPrivacy /> },
        ]
      }
    ]
  },
  {
    path: '/super-admin',
    element: (
      <SuperAdminAuthProvider>
        <SuperAdminRoute />
      </SuperAdminAuthProvider>
    ),
    children: [
      {
        element: <SuperAdminLayout />,
        children: [
          { index: true, element: <Navigate to="/super-admin/dashboard" replace /> },
          { path: 'dashboard', element: lazyLoad(SuperAdminDashboardPage) },
          { path: 'tenants', element: lazyLoad(TenantsPage) },
          { path: 'tenants/:id', element: lazyLoad(TenantDetailPage) },
          { path: 'audit-log', element: lazyLoad(AuditLogPage) },
          { path: 'accounts', element: lazyLoad(AccountsPage) },
        ]
      }
    ]
  },
  {
    path: '/super-admin/login',
    element: (
      <SuperAdminAuthProvider>
        {lazyLoad(SuperAdminLoginPage)}
      </SuperAdminAuthProvider>
    )
  },
  {
    path: '*',
    element: <NotFound />
  }
]);


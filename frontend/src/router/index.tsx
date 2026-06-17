
import { createBrowserRouter, Navigate } from 'react-router-dom';

import ProtectedRoute from '../components/shared/ProtectedRoute';
import PublicLayout from '../components/layout/PublicLayout';
import AdminLayout from '../components/layout/AdminLayout';
import ResellerLayout from '../components/layout/ResellerLayout';
import CustomerLayout from '../components/layout/CustomerLayout';

import LandingPage from '../pages/public/LandingPage';
import LoginPage from '../pages/public/LoginPage';
import RegisterPage from '../pages/public/RegisterPage';

import AdminDashboard from '../pages/admin/DashboardPage';
import AdminCustomers from '../pages/admin/CustomersPage';
import AdminPackages from '../pages/admin/PackagesPage';
import AdminPayments from '../pages/admin/PaymentsPage';
import AdminVouchers from '../pages/admin/VouchersPage';
import AdminSessions from '../pages/admin/SessionsPage';

import ResellerDashboard from '../pages/reseller/ResellerDashboard';
import ResellerCustomers from '../pages/reseller/MyCustomersPage';
import ResellerPayments from '../pages/reseller/ResellerPaymentsPage';
import ResellerVouchers from '../pages/reseller/ResellerVouchersPage';

import CustomerDashboard from '../pages/customer/DashboardPage';
import CustomerBuyPackage from '../pages/customer/BuyPackagePage';
import CustomerPaymentStatus from '../pages/customer/PaymentStatusPage';
import CustomerVouchers from '../pages/customer/VouchersPage';
import CustomerProfile from '../pages/customer/ProfilePage';

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
    ],
  },
  {
    path: '/admin',
    element: <ProtectedRoute allowedRoles={['admin']} />,
    children: [
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
          { path: 'profile', element: <CustomerProfile /> },
        ]
      }
    ]
  },
  {
    path: '*',
    element: <NotFound />
  }
]);

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ADMIN_ROUTES } from './config';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { AdminLoginPage } from './pages/AdminLoginPage';
import { AdminUserDetailsPage } from './pages/AdminUserDetailsPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={ADMIN_ROUTES.login} element={<AdminLoginPage />} />
        <Route path={ADMIN_ROUTES.dashboard} element={<AdminDashboardPage />} />
        <Route path="/admin/users/:hhId" element={<AdminUserDetailsPage />} />
        <Route path="*" element={<Navigate to={ADMIN_ROUTES.login} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

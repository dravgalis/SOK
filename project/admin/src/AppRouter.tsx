import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ADMIN_ROUTES } from './config';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { AdminLoginPage } from './pages/AdminLoginPage';
import { AdminUserOperationsPage } from './pages/AdminUserOperationsPage';
import { AdminUserDetailsPage } from './pages/AdminUserDetailsPage';
import { AdminVacancyResponsesPage } from './pages/AdminVacancyResponsesPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={ADMIN_ROUTES.login} element={<AdminLoginPage />} />
        <Route path={ADMIN_ROUTES.dashboard} element={<AdminDashboardPage />} />
        <Route path="/admin/users/:hhId" element={<AdminUserDetailsPage />} />
        <Route path="/admin/users/:hhId/operations" element={<AdminUserOperationsPage />} />
        <Route path="/admin/users/:hhId/vacancies/:vacancyId/responses" element={<AdminVacancyResponsesPage />} />
        <Route path="*" element={<Navigate to={ADMIN_ROUTES.login} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

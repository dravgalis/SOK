import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { APP_ROUTES } from './config';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path={APP_ROUTES.login} element={<LoginPage />} />
        <Route path={APP_ROUTES.app} element={<DashboardPage />} />
        <Route path="*" element={<Navigate to={APP_ROUTES.login} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

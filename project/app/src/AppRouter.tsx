import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { APP_ROUTES } from './config';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { OperationsPage } from './pages/OperationsPage';
import { PaymentReturnPage } from './pages/PaymentReturnPage';
import { ThemeSettingsPage } from './pages/ThemeSettingsPage';
import { VacancyDetailsPage } from './pages/VacancyDetailsPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path={APP_ROUTES.app} element={<DashboardPage />} />
        <Route path={APP_ROUTES.operations} element={<OperationsPage />} />
        <Route path={APP_ROUTES.theme} element={<ThemeSettingsPage />} />
        <Route path={APP_ROUTES.paymentReturn} element={<PaymentReturnPage />} />
        <Route path={APP_ROUTES.vacancyDetails} element={<VacancyDetailsPage />} />
        <Route path="*" element={<Navigate to={APP_ROUTES.login} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

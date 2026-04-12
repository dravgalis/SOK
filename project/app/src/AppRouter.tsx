import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from './config';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';
import { OperationsPage } from './pages/OperationsPage';
import { PaymentReturnPage } from './pages/PaymentReturnPage';
import { ThemeSettingsPage } from './pages/ThemeSettingsPage';
import { VacancyDetailsPage } from './pages/VacancyDetailsPage';
import { applyTheme, isThemeKey } from './theme';

export function AppRouter() {
  useEffect(() => {
    const syncSelectedTheme = async () => {
      try {
        const response = await fetch(APP_ENDPOINTS.selectedTheme, { credentials: 'include' });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { selected_theme?: unknown };
        if (isThemeKey(payload.selected_theme)) {
          applyTheme(payload.selected_theme, true);
        }
      } catch {
        // ignore sync errors and keep local fallback theme
      }
    };

    void syncSelectedTheme();
  }, []);

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

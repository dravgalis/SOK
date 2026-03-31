import { Navigate, Route, Routes } from 'react-router-dom';
import { APP_ROUTES } from './config/api';
import { HhCallbackPage } from './pages/HhCallbackPage';
import { HhLoginPage } from './pages/HhLoginPage';

export function AppRouter() {
  return (
    <Routes>
      <Route path={APP_ROUTES.root} element={<HhLoginPage />} />
      <Route path={APP_ROUTES.hhCallback} element={<HhCallbackPage />} />
      <Route path="*" element={<Navigate to={APP_ROUTES.root} replace />} />
    </Routes>
  );
}

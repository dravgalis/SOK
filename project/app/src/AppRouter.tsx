import { useEffect, useState } from 'react';
import { APP_ROUTES } from './config';
import { AppPage } from './pages/AppPage';
import { LoginPage } from './pages/LoginPage';

export function AppRouter() {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  if (path === APP_ROUTES.app) {
    return <AppPage />;
  }

  return <LoginPage />;
}

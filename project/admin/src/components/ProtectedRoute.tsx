import { Navigate } from 'react-router-dom';
import { isAdminAuthenticated } from '../auth';

type ProtectedRouteProps = {
  children: JSX.Element;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  if (!isAdminAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  return children;
}

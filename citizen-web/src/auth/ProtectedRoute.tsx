import { Navigate, useLocation } from 'react-router-dom';
import { loginPath } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useCitizenAuth();
  const location = useLocation();
  if (auth.isLoading)
    return (
      <div className="session-splash" role="status">
        Restoring your session…
      </div>
    );
  if (!auth.isAuthenticated) {
    return <Navigate replace to={loginPath(`${location.pathname}${location.search}`)} />;
  }
  return children;
}

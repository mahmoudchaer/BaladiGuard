import { Navigate, useLocation } from 'react-router-dom';
import { loginPath } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { useI18n } from '@/i18n/LocaleProvider';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useCitizenAuth();
  const location = useLocation();
  const { t } = useI18n();
  if (auth.isLoading)
    return (
      <div className="session-splash" role="status">
        {t('track.restoring')}
      </div>
    );
  if (!auth.isAuthenticated) {
    return <Navigate replace to={loginPath(`${location.pathname}${location.search}`)} />;
  }
  return children;
}

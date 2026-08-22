import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { homePathForRole, type StaffRole } from '@/services/auth';

type ProtectedRouteProps = {
  children: ReactNode;
  role?: StaffRole;
  allowedRoles?: StaffRole[];
};

export function ProtectedRoute({ children, role, allowedRoles }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, session } = useStaffAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const permitted = allowedRoles ?? (role ? [role] : undefined);
  if (permitted && session?.role && !permitted.includes(session.role)) {
    return (
      <Navigate to={homePathForRole(session.role)} replace state={{ accessDenied: true }} />
    );
  }

  return children;
}

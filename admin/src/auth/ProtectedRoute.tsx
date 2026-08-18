import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { homePathForRole, type StaffRole } from '@/services/auth';

type ProtectedRouteProps = {
  children: ReactNode;
  allowedRoles?: StaffRole[];
};

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, session } = useStaffAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (allowedRoles && session?.role && !allowedRoles.includes(session.role)) {
    return <Navigate to={homePathForRole(session.role)} replace />;
  }

  return children;
}

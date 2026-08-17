import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import type { StaffRole } from '@/services/auth';

type ProtectedRouteProps = {
  children: ReactNode;
  role?: StaffRole;
};

export function ProtectedRoute({ children, role }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, session } = useStaffAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (role && session?.role !== role) {
    return <Navigate to="/" replace />;
  }

  return children;
}

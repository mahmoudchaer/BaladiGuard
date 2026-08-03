import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { StaffAuthContext } from '@/auth/staffAuthState';
import {
  STAFF_SESSION_CLEARED_EVENT,
  getStoredStaffSession,
  loginStaff,
  logoutStaff,
  type StaffSession,
} from '@/services/auth';

type StaffAuthProviderProps = {
  children: ReactNode;
};

export function StaffAuthProvider({ children }: StaffAuthProviderProps) {
  const [session, setSession] = useState<StaffSession | null>(() => getStoredStaffSession());

  const login = useCallback(async (username: string, password: string) => {
    const result = await loginStaff(username, password);

    if (result.ok) {
      setSession(result.session);
    }

    return result;
  }, []);

  const logout = useCallback(() => {
    void logoutStaff();
    setSession(null);
  }, []);

  useEffect(() => {
    const handleSessionCleared = () => setSession(null);

    window.addEventListener(STAFF_SESSION_CLEARED_EVENT, handleSessionCleared);
    return () => window.removeEventListener(STAFF_SESSION_CLEARED_EVENT, handleSessionCleared);
  }, []);

  const value = useMemo(
    () => ({
      session,
      isAuthenticated: session !== null,
      login,
      logout,
    }),
    [login, logout, session],
  );

  return <StaffAuthContext.Provider value={value}>{children}</StaffAuthContext.Provider>;
}

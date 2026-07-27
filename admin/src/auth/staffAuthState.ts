import { createContext } from 'react';
import type { LoginResult, StaffSession } from '@/services/auth';

export type StaffAuthContextValue = {
  session: StaffSession | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => LoginResult;
  logout: () => void;
};

export const StaffAuthContext = createContext<StaffAuthContextValue | null>(null);

import { useContext } from 'react';
import { StaffAuthContext } from '@/auth/staffAuthState';

export function useStaffAuth() {
  const context = useContext(StaffAuthContext);

  if (!context) {
    throw new Error('useStaffAuth must be used inside StaffAuthProvider');
  }

  return context;
}

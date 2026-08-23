import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { ApiError, setUnauthorizedHandler } from '@/services/api';
import { getMe, logout as logoutApi, updateMe, verifyOtp } from '@/services/citizenAuth';
import { completeFirebasePhoneOtp } from '@/services/firebasePhoneAuth';
import type { CitizenProfile, CitizenProfilePatch, OtpVerifyOptions } from '@/types/citizen';

type AuthValue = {
  profile: CitizenProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  applyOtp: (
    challengeId: string,
    code: string,
    options: OtpVerifyOptions,
  ) => Promise<CitizenProfile>;
  applyFirebaseOtp: (
    challengeId: string,
    code: string,
    purpose: 'LOGIN_OR_SIGNUP' | 'CHANGE_PHONE',
    options: OtpVerifyOptions,
  ) => Promise<CitizenProfile>;
  refresh: () => Promise<CitizenProfile | null>;
  updateProfile: (patch: CitizenProfilePatch) => Promise<CitizenProfile>;
  setProfile: (profile: CitizenProfile | null) => void;
  logout: () => Promise<void>;
};

const Context = createContext<AuthValue | null>(null);

export function CitizenAuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<CitizenProfile | null>(null);
  const [isLoading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const next = await getMe();
      setProfile(next);
      return next;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setProfile(null);
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh().finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    setUnauthorizedHandler(() => setProfile(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      profile,
      isLoading,
      isAuthenticated: Boolean(profile),
      applyOtp: async (challengeId, code, options) => {
        const next = await verifyOtp(challengeId, code, options);
        setProfile(next);
        return next;
      },
      applyFirebaseOtp: async (challengeId, code, purpose, options) => {
        const next = await completeFirebasePhoneOtp(challengeId, code, purpose, options);
        setProfile(next);
        return next;
      },
      refresh,
      updateProfile: async (patch) => {
        const next = await updateMe(patch);
        setProfile(next);
        return next;
      },
      setProfile,
      logout: async () => {
        try {
          await logoutApi();
        } finally {
          setProfile(null);
        }
      },
    }),
    [profile, isLoading, refresh],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

// Context and hook intentionally live together so the provider contract stays atomic.
// eslint-disable-next-line react-refresh/only-export-components
export function useCitizenAuth(): AuthValue {
  const value = useContext(Context);
  if (!value) throw new Error('useCitizenAuth must be used within CitizenAuthProvider');
  return value;
}

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { CitizenProfile, CitizenSession } from '@/types/citizen';
import {
  getCitizenMe,
  logoutCitizen,
  profileFromVerifyResponse,
  updateCitizenProfile,
  verifyCitizenOtp,
  type CitizenAuthApiError,
} from '@/services/api/citizenAuth';
import {
  setCitizenAccessTokenProvider,
  setCitizenUnauthorizedHandler,
} from '@/services/api/http';
import {
  buildCitizenSession,
  clearCitizenSession,
  loadCitizenSession,
  saveCitizenSession,
} from '@/services/citizenSession';

type CitizenAuthContextValue = {
  session: CitizenSession | null;
  profile: CitizenProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  contributionReady: boolean;
  accessToken: string | null;
  restoreSession: () => Promise<void>;
  applyVerifyResponse: (response: Awaited<ReturnType<typeof verifyCitizenOtp>>) => Promise<void>;
  completeFullName: (fullName: string) => Promise<CitizenProfile>;
  logout: () => Promise<void>;
  clearSessionLocally: () => Promise<void>;
};

const CitizenAuthContext = createContext<CitizenAuthContextValue | null>(null);

export function CitizenAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<CitizenSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSessionLocally = useCallback(async () => {
    setSession(null);
    await clearCitizenSession();
  }, []);

  const restoreSession = useCallback(async () => {
    setIsLoading(true);
    try {
      const stored = await loadCitizenSession();
      if (!stored) {
        setSession(null);
        return;
      }

      try {
        const profile = await getCitizenMe(stored.accessToken);
        const next = buildCitizenSession(
          stored.accessToken,
          Math.max(1, Math.floor((stored.expiresAt - Date.now()) / 1000)),
          profile,
        );
        setSession(next);
        await saveCitizenSession(next);
      } catch (error) {
        const authError = error as CitizenAuthApiError;
        if (authError?.status === 401 || authError?.code === 'UNAUTHORIZED') {
          await clearCitizenSession();
          setSession(null);
          return;
        }
        // Offline / transient: keep cached session so contribution gates still work.
        setSession(stored);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  useEffect(() => {
    setCitizenAccessTokenProvider(() => session?.accessToken ?? null);
    setCitizenUnauthorizedHandler(() => {
      void clearSessionLocally();
    });
    return () => {
      setCitizenAccessTokenProvider(null);
      setCitizenUnauthorizedHandler(null);
    };
  }, [session?.accessToken, clearSessionLocally]);

  const applyVerifyResponse = useCallback(
    async (response: Awaited<ReturnType<typeof verifyCitizenOtp>>) => {
      const profile = profileFromVerifyResponse(response);
      const next = buildCitizenSession(response.accessToken, response.expiresIn, profile);
      setSession(next);
      await saveCitizenSession(next);
    },
    [],
  );

  const completeFullName = useCallback(
    async (fullName: string) => {
      if (!session?.accessToken) {
        throw new Error('Sign in before updating your name.');
      }
      const profile = await updateCitizenProfile(session.accessToken, { fullName });
      const next: CitizenSession = {
        ...session,
        profile,
      };
      setSession(next);
      await saveCitizenSession(next);
      return profile;
    },
    [session],
  );

  const logout = useCallback(async () => {
    const token = session?.accessToken;
    if (token) {
      try {
        await logoutCitizen(token);
      } catch {
        // Still clear local session on network / already-revoked failures.
      }
    }
    await clearSessionLocally();
  }, [session?.accessToken, clearSessionLocally]);

  const value = useMemo<CitizenAuthContextValue>(
    () => ({
      session,
      profile: session?.profile ?? null,
      isLoading,
      isAuthenticated: Boolean(session?.accessToken),
      contributionReady: Boolean(session?.profile?.contributionReady),
      accessToken: session?.accessToken ?? null,
      restoreSession,
      applyVerifyResponse,
      completeFullName,
      logout,
      clearSessionLocally,
    }),
    [
      session,
      isLoading,
      restoreSession,
      applyVerifyResponse,
      completeFullName,
      logout,
      clearSessionLocally,
    ],
  );

  return <CitizenAuthContext.Provider value={value}>{children}</CitizenAuthContext.Provider>;
}

export function useCitizenAuth(): CitizenAuthContextValue {
  const value = useContext(CitizenAuthContext);
  if (!value) {
    throw new Error('useCitizenAuth must be used within CitizenAuthProvider');
  }
  return value;
}

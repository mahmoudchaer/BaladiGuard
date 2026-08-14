import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { CitizenProfile, CitizenProfileUpdatePayload, CitizenSession } from '@/types/citizen';
import {
  getCitizenMe,
  logoutCitizen,
  profileFromVerifyResponse,
  updateCitizenProfile,
  verifyCitizenOtp,
  type CitizenAuthApiError,
} from '@/services/api/citizenAuth';
import { setCitizenAccessTokenProvider, setCitizenUnauthorizedHandler } from '@/services/api/http';
import {
  buildCitizenSession,
  clearCitizenSession,
  isContributionReadyFromProfile,
  loadCitizenSession,
  migrateCitizenSession,
  saveCitizenSession,
} from '@/services/citizenSession';
import { clearReportDraft } from '@/services/reportDraft';

type CitizenAuthContextValue = {
  session: CitizenSession | null;
  profile: CitizenProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  contributionReady: boolean;
  accessToken: string | null;
  restoreSession: () => Promise<void>;
  refreshProfile: () => Promise<CitizenProfile | null>;
  applyVerifyResponse: (response: Awaited<ReturnType<typeof verifyCitizenOtp>>) => Promise<void>;
  updateProfile: (patch: CitizenProfileUpdatePayload) => Promise<CitizenProfile>;
  /** Clears local session. By default also clears this user's report draft (#258). */
  logout: (options?: { retainReportDraft?: boolean }) => Promise<void>;
  clearSessionLocally: (options?: { retainReportDraft?: boolean }) => Promise<void>;
};

const CitizenAuthContext = createContext<CitizenAuthContextValue | null>(null);

export function CitizenAuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<CitizenSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clearSessionLocally = useCallback(
    async (options?: { retainReportDraft?: boolean }) => {
      const userId = session?.profile?.userId;
      setSession(null);
      await clearCitizenSession();
      if (userId && !options?.retainReportDraft) {
        await clearReportDraft(userId);
      }
    },
    [session?.profile?.userId],
  );

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
          // Session invalid — drop local identity; keep draft by user id only if token was still keyed.
          // Without a known owner match we only clear session (draft stays under its prior key).
          await clearCitizenSession();
          setSession(null);
          return;
        }
        // Offline / transient: keep cached session (with #270 readiness migration)
        // so contribution gates still work without a successful profile refresh.
        const migrated = migrateCitizenSession(stored);
        setSession(migrated);
        if (migrated.profile.contributionReady !== stored.profile.contributionReady) {
          await saveCitizenSession(migrated);
        }
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
      // Different account on the same device must not inherit another user's in-memory draft UI;
      // drafts are already isolated by SecureStore userId key.
      const next = buildCitizenSession(response.accessToken, response.expiresIn, profile);
      setSession(next);
      await saveCitizenSession(next);
    },
    [],
  );

  const applyProfileToSession = useCallback(
    async (profile: CitizenProfile) => {
      if (!session?.accessToken) {
        throw new Error('Sign in before updating your profile.');
      }
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

  const updateProfile = useCallback(
    async (patch: CitizenProfileUpdatePayload) => {
      if (!session?.accessToken) {
        throw new Error('Sign in before updating your profile.');
      }
      const profile = await updateCitizenProfile(session.accessToken, patch);
      return applyProfileToSession(profile);
    },
    [session, applyProfileToSession],
  );

  const refreshProfile = useCallback(async () => {
    if (!session?.accessToken) {
      return null;
    }
    try {
      const profile = await getCitizenMe(session.accessToken);
      await applyProfileToSession(profile);
      return profile;
    } catch (error) {
      const authError = error as CitizenAuthApiError;
      if (authError?.status === 401 || authError?.code === 'UNAUTHORIZED') {
        await clearSessionLocally();
        return null;
      }
      throw error;
    }
  }, [session, applyProfileToSession, clearSessionLocally]);

  const logout = useCallback(
    async (options?: { retainReportDraft?: boolean }) => {
      const token = session?.accessToken;
      if (token) {
        try {
          await logoutCitizen(token);
        } catch {
          // Still clear local session on network / already-revoked failures.
        }
      }
      await clearSessionLocally(options);
    },
    [session?.accessToken, clearSessionLocally],
  );

  const value = useMemo<CitizenAuthContextValue>(
    () => ({
      session,
      profile: session?.profile ?? null,
      isLoading,
      isAuthenticated: Boolean(session?.accessToken),
      contributionReady: session ? isContributionReadyFromProfile(session.profile) : false,
      accessToken: session?.accessToken ?? null,
      restoreSession,
      refreshProfile,
      applyVerifyResponse,
      updateProfile,
      logout,
      clearSessionLocally,
    }),
    [
      session,
      isLoading,
      restoreSession,
      refreshProfile,
      applyVerifyResponse,
      updateProfile,
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

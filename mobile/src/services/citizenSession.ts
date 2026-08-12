import * as SecureStore from 'expo-secure-store';

import type { CitizenProfile, CitizenSession } from '@/types/citizen';

export const CITIZEN_SESSION_STORAGE_KEY = 'baladiguard.citizenSession';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function isCitizenProfile(value: unknown): value is CitizenProfile {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.userId === 'string' &&
    typeof value.phone === 'string' &&
    typeof value.contributionReady === 'boolean' &&
    typeof value.active === 'boolean'
  );
}

function isCitizenSession(value: unknown): value is CitizenSession {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value.accessToken === 'string' &&
    typeof value.expiresAt === 'number' &&
    isCitizenProfile(value.profile)
  );
}

/**
 * Contribution readiness matches the #270 backend contract: active account +
 * verified phone. Full name is optional and must not gate contribution.
 */
export function isContributionReadyFromProfile(
  profile: Pick<CitizenProfile, 'active' | 'phoneVerifiedAt'>,
): boolean {
  return Boolean(profile.active && String(profile.phoneVerifiedAt ?? '').trim());
}

/**
 * Migrate pre-#270 cached profiles that still store `contributionReady: false`
 * for verified phone-only citizens. Does not weaken expiry or 401 handling.
 */
export function migrateCitizenProfile(profile: CitizenProfile): CitizenProfile {
  const contributionReady = isContributionReadyFromProfile(profile);
  if (profile.contributionReady === contributionReady) {
    return profile;
  }
  return { ...profile, contributionReady };
}

export function migrateCitizenSession(session: CitizenSession): CitizenSession {
  const profile = migrateCitizenProfile(session.profile);
  if (profile === session.profile) {
    return session;
  }
  return { ...session, profile };
}

export async function loadCitizenSession(): Promise<CitizenSession | null> {
  let raw: string | null;
  try {
    raw = await SecureStore.getItemAsync(CITIZEN_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }

  if (!raw) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isCitizenSession(parsed)) {
      await clearCitizenSession();
      return null;
    }
    if (parsed.expiresAt <= Date.now()) {
      await clearCitizenSession();
      return null;
    }
    const migrated = migrateCitizenSession(parsed);
    if (migrated.profile.contributionReady !== parsed.profile.contributionReady) {
      // Persist the #270 readiness migration so offline restores stay correct.
      await saveCitizenSession(migrated);
    }
    return migrated;
  } catch {
    await clearCitizenSession();
    return null;
  }
}

export async function saveCitizenSession(session: CitizenSession): Promise<void> {
  await SecureStore.setItemAsync(
    CITIZEN_SESSION_STORAGE_KEY,
    JSON.stringify(migrateCitizenSession(session)),
  );
}

export async function clearCitizenSession(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(CITIZEN_SESSION_STORAGE_KEY);
  } catch {
    // Best-effort clear; callers still drop in-memory session.
  }
}

export function buildCitizenSession(
  accessToken: string,
  expiresInSeconds: number,
  profile: CitizenProfile,
): CitizenSession {
  return {
    accessToken,
    expiresAt: Date.now() + expiresInSeconds * 1000,
    profile: migrateCitizenProfile(profile),
  };
}

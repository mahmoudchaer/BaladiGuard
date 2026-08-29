import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildCitizenSession,
  clearCitizenSession,
  CITIZEN_SESSION_STORAGE_KEY,
  loadCitizenSession,
  saveCitizenSession,
} from '@/services/citizenSession';
import {
  __getSecureStoreMock,
  __resetSecureStoreMock,
  __setSecureStoreError,
} from '@/test/mocks/expo-secure-store';
import type { CitizenProfile } from '@/types/citizen';

const profile: CitizenProfile = {
  userId: 'usr_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T12:00:00Z',
  fullName: 'Ada Citizen',
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE', announcements: false },
  publicNameVisible: false,
  leaderboardOptIn: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T12:00:00Z',
  updatedAt: '2026-08-01T12:00:00Z',
};

describe('citizenSession', () => {
  beforeEach(() => {
    __resetSecureStoreMock();
  });

  it('persists and restores a session from SecureStore', async () => {
    const session = buildCitizenSession('tok_1', 3600, profile);
    await saveCitizenSession(session);

    const restored = await loadCitizenSession();
    expect(restored?.accessToken).toBe('tok_1');
    expect(restored?.profile.userId).toBe('usr_1');
    expect(__getSecureStoreMock().has(CITIZEN_SESSION_STORAGE_KEY)).toBe(true);
  });

  it('persists across unsigned development simulator restarts when Keychain is unavailable', async () => {
    __setSecureStoreError(new Error('A required entitlement is not present.'));
    const session = buildCitizenSession('tok_dev', 3600, profile);

    await saveCitizenSession(session);
    const restored = await loadCitizenSession();

    expect(restored?.accessToken).toBe('tok_dev');
    expect(restored?.profile.userId).toBe('usr_1');
  });

  it('clears expired and invalid sessions', async () => {
    await saveCitizenSession({
      accessToken: 'tok_old',
      expiresAt: Date.now() - 1000,
      profile,
    });
    expect(await loadCitizenSession()).toBeNull();

    __getSecureStoreMock().set(CITIZEN_SESSION_STORAGE_KEY, '{not-json');
    expect(await loadCitizenSession()).toBeNull();
  });

  it('clears the stored session on logout', async () => {
    await saveCitizenSession(buildCitizenSession('tok_1', 3600, profile));
    await clearCitizenSession();
    expect(await loadCitizenSession()).toBeNull();
  });

  it('migrates pre-#270 cached contributionReady for verified phone-only profiles', async () => {
    const { CITIZEN_SESSION_STORAGE_KEY } = await import('@/services/citizenSession');
    const { __getSecureStoreMock } = await import('@/test/mocks/expo-secure-store');
    __getSecureStoreMock().set(
      CITIZEN_SESSION_STORAGE_KEY,
      JSON.stringify({
        accessToken: 'tok_legacy',
        expiresAt: Date.now() + 3_600_000,
        profile: {
          ...profile,
          fullName: null,
          contributionReady: false,
        },
      }),
    );

    const restored = await loadCitizenSession();
    expect(restored?.profile.fullName).toBeNull();
    expect(restored?.profile.contributionReady).toBe(true);
  });
});

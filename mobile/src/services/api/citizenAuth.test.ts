import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ACCOUNT_INACTIVE_MESSAGE,
  CitizenAuthApiError,
  OTP_EXPIRED_MESSAGE,
  OTP_INVALID_MESSAGE,
  OTP_NETWORK_MESSAGE,
  OTP_RATE_LIMITED_MESSAGE,
  PHONE_UNAVAILABLE_MESSAGE,
  getCitizenMe,
  logoutCitizen,
  requestCitizenOtp,
  updateCitizenProfile,
  verifyCitizenOtp,
} from '@/services/api/citizenAuth';

const { appConfig } = vi.hoisted(() => ({
  appConfig: {
    apiBaseUrl: 'http://localhost:8000/v1',
    enableMockApi: false,
    appVersion: '0.1.0',
  },
}));

vi.mock('@/services/config', () => ({
  appConfig,
}));

const profile = {
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

describe('citizenAuth API client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('requests an OTP with phone, region, and LOGIN_OR_SIGNUP purpose', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({
        challengeId: 'ch_1',
        expiresIn: 300,
        message: 'If the number can receive codes, a verification code was sent.',
      }),
      headers: { get: () => null },
    } as unknown as Response);

    const result = await requestCitizenOtp({ phone: '70123456', region: 'LB' });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/auth/otp/request',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          phone: '70123456',
          purpose: 'LOGIN_OR_SIGNUP',
          region: 'LB',
        }),
      }),
    );
    expect(result.challengeId).toBe('ch_1');
  });

  it('verifies an OTP and returns the session payload', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        accessToken: 'tok_1',
        tokenType: 'Bearer',
        expiresIn: 2592000,
        ...profile,
      }),
      headers: { get: () => null },
    } as unknown as Response);

    const result = await verifyCitizenOtp({
      challengeId: 'ch_1',
      code: '123456',
      acceptLegal: true,
      legalLocale: 'en',
    });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/auth/otp/verify',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          challengeId: 'ch_1',
          code: '123456',
          acceptLegal: true,
          legalLocale: 'en',
        }),
      }),
    );
    expect(result.accessToken).toBe('tok_1');
    expect(result.contributionReady).toBe(true);
  });

  it('maps invalid and expired OTP codes to safe messages', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error: { code: 'INVALID_OTP', message: 'secret' } }),
      headers: { get: () => null },
      clone() {
        return this;
      },
    } as unknown as Response);

    await expect(verifyCitizenOtp({ challengeId: 'ch_1', code: '000000' })).rejects.toMatchObject({
      message: OTP_INVALID_MESSAGE,
      code: 'INVALID_OTP',
    });

    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ error: { code: 'OTP_EXPIRED', message: 'secret' } }),
      headers: { get: () => null },
      clone() {
        return this;
      },
    } as unknown as Response);

    await expect(verifyCitizenOtp({ challengeId: 'ch_1', code: '123456' })).rejects.toMatchObject({
      message: OTP_EXPIRED_MESSAGE,
      code: 'OTP_EXPIRED',
    });
  });

  it('maps throttling responses with Retry-After', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({
        error: { code: 'RATE_LIMITED', message: 'Too many verification requests.' },
      }),
      headers: { get: (name: string) => (name === 'Retry-After' ? '45' : null) },
      clone() {
        return this;
      },
    } as unknown as Response);

    await expect(requestCitizenOtp({ phone: '+96170123456' })).rejects.toEqual(
      expect.objectContaining({
        message: 'Too many verification requests.',
        code: 'RATE_LIMITED',
        retryAfterSeconds: 45,
      }),
    );
  });

  it('maps inactive account and offline failures', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ error: { code: 'ACCOUNT_INACTIVE', message: 'inactive' } }),
      headers: { get: () => null },
      clone() {
        return this;
      },
    } as unknown as Response);

    await expect(verifyCitizenOtp({ challengeId: 'ch_1', code: '123456' })).rejects.toMatchObject({
      message: ACCOUNT_INACTIVE_MESSAGE,
    });

    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'));
    await expect(requestCitizenOtp({ phone: '+96170123456' })).rejects.toMatchObject({
      message: OTP_NETWORK_MESSAGE,
      code: 'NETWORK_ERROR',
    });
  });

  it('loads the citizen profile and logs out', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => profile,
        headers: { get: () => null },
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: { get: () => null },
      } as unknown as Response);

    await expect(getCitizenMe('tok_1')).resolves.toEqual(profile);
    await expect(logoutCitizen('tok_1')).resolves.toBeUndefined();
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/v1/citizen/auth/logout',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('patches full name on the profile', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ ...profile, fullName: 'Ada Lovelace', contributionReady: true }),
      headers: { get: () => null },
    } as unknown as Response);

    const result = await updateCitizenProfile('tok_1', { fullName: 'Ada Lovelace' });
    expect(result.fullName).toBe('Ada Lovelace');
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/me',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ fullName: 'Ada Lovelace' }),
      }),
    );
  });

  it('patches optional email, preferences, and public visibility', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({
        ...profile,
        email: null,
        publicNameVisible: true,
        notificationPreferences: { ticketUpdates: 'SMS', announcements: true },
      }),
      headers: { get: () => null },
    } as unknown as Response);

    await updateCitizenProfile('tok_1', {
      email: null,
      publicNameVisible: true,
      notificationPreferences: { ticketUpdates: 'SMS', announcements: true },
    });

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/me',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          email: null,
          notificationPreferences: { ticketUpdates: 'SMS', announcements: true },
          publicNameVisible: true,
        }),
      }),
    );
  });

  it('maps PHONE_UNAVAILABLE conflicts to a safe message', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: { code: 'PHONE_UNAVAILABLE', message: 'secret' } }),
      headers: { get: () => null },
      clone() {
        return this;
      },
    } as unknown as Response);

    await expect(verifyCitizenOtp({ challengeId: 'ch_1', code: '123456' })).rejects.toMatchObject({
      message: PHONE_UNAVAILABLE_MESSAGE,
      code: 'PHONE_UNAVAILABLE',
    });
  });

  it('exposes CitizenAuthApiError for callers', () => {
    const error = new CitizenAuthApiError(OTP_RATE_LIMITED_MESSAGE, {
      code: 'RATE_LIMITED',
      status: 429,
      retryAfterSeconds: 30,
    });
    expect(error).toBeInstanceOf(Error);
    expect(error.retryAfterSeconds).toBe(30);
  });
});

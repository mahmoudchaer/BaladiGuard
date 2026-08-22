import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getMe, requestOtp, verifyOtp } from '@/services/citizenAuth';

const profile = {
  userId: 'cit_1',
  phone: '+96170123456',
  phoneVerifiedAt: '2026-08-01T00:00:00Z',
  fullName: null,
  email: null,
  notificationPreferences: { ticketUpdates: 'NONE' as const, announcements: false },
  publicNameVisible: false,
  active: true,
  contributionReady: true,
  createdAt: '2026-08-01T00:00:00Z',
  updatedAt: '2026-08-01T00:00:00Z',
};

describe('citizen web authentication API', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('requests the existing phone OTP contract with cookies enabled', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ challengeId: 'chl_1', expiresIn: 300, message: 'Sent' }), {
        status: 202,
      }),
    );
    await requestOtp('70123456', 'LB');
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/v1/citizen/auth/otp/request',
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
        body: JSON.stringify({ phone: '70123456', region: 'LB', purpose: 'LOGIN_OR_SIGNUP' }),
      }),
    );
  });

  it('opts verification into HttpOnly cookie mode and does not need a bearer token', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify(profile), { status: 200 }));
    await expect(
      verifyOtp('chl_1', '123456', { acceptLegal: true, legalLocale: 'en' }),
    ).resolves.toEqual(profile);
    const init = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(init?.headers).get('X-Citizen-Session-Mode')).toBe('cookie');
    expect(new Headers(init?.headers).has('Authorization')).toBe(false);
    expect(init?.credentials).toBe('include');
    expect(init?.body).toBe(
      JSON.stringify({
        challengeId: 'chl_1',
        code: '123456',
        acceptLegal: true,
        legalLocale: 'en',
      }),
    );
  });

  it('restores the browser session through the profile endpoint', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(profile), { status: 200 }),
    );
    await expect(getMe()).resolves.toEqual(profile);
  });
});

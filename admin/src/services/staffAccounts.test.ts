import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  createStaffAccount,
  listStaffAccounts,
  updateStaffAccount,
} from '@/services/staffAccounts';

describe('staff account client', () => {
  beforeEach(() => {
    window.localStorage.setItem(
      'baladiguard.staffSession',
      JSON.stringify({
        username: 'admin',
        name: 'Admin',
        staffId: 'staff_admin',
        role: 'administrator',
        municipalityId: null,
        departmentIds: null,
        signedInAt: 'now',
        accessToken: 'secret-token',
      }),
    );
  });

  it('uses the protected contract and preserves partial PATCH payloads', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ staffId: 'staff_1' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await updateStaffAccount('staff_1', { departmentIds: ['roads'] });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/v1/admin/staff-accounts/staff_1'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ departmentIds: ['roads'] }),
      }),
    );
  });

  it('surfaces duplicate and not-found API messages', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: { code: 'STAFF_USERNAME_CONFLICT', message: 'Username already exists.' },
            }),
            { status: 409, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );
    await expect(
      createStaffAccount({
        username: 'taken',
        name: 'Taken',
        email: 't@example.test',
        password: 'secret-pass',
        role: 'administrator',
        municipalityId: null,
        departmentIds: null,
      }),
    ).rejects.toThrow('Username already exists.');
  });

  it('clears an expired session on 401', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: { code: 'UNAUTHORIZED', message: 'Session expired.' },
            }),
            { status: 401, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );
    await expect(listStaffAccounts()).rejects.toThrow('Session expired.');
    expect(window.localStorage.getItem('baladiguard.staffSession')).toBeNull();
  });
});

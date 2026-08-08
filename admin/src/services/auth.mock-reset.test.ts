import { beforeEach, describe, expect, it, vi } from 'vitest';

import { config } from '@/services/config';
import { confirmStaffPasswordReset, loginStaff, resetMockStaffAuthState } from '@/services/auth';

describe('mock staff password reset', () => {
  beforeEach(() => {
    resetMockStaffAuthState();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    });
  });

  it('persists the new password for subsequent mock logins', async () => {
    if (!config.useMockData) {
      return;
    }

    const reset = await confirmStaffPasswordReset({
      username: config.staffAuth.username,
      code: '123456',
      newPassword: 'replacement-password-99',
    });
    expect(reset.ok).toBe(true);

    const oldPasswordLogin = await loginStaff(config.staffAuth.username, config.staffAuth.password);
    expect(oldPasswordLogin.ok).toBe(false);

    const newPasswordLogin = await loginStaff(config.staffAuth.username, 'replacement-password-99');
    expect(newPasswordLogin.ok).toBe(true);
  });
});

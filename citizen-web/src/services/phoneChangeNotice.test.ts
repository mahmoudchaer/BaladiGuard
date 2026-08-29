import { describe, expect, it, vi } from 'vitest';
import { consumePhoneChangedNotice, markPhoneChangedNotice } from '@/services/phoneChangeNotice';

describe('phone change notice storage', () => {
  it('does not throw when session storage is unavailable', () => {
    const storage = {
      getItem: vi.fn(() => {
        throw new DOMException('Blocked', 'SecurityError');
      }),
      setItem: vi.fn(() => {
        throw new DOMException('Blocked', 'SecurityError');
      }),
      removeItem: vi.fn(),
    };
    vi.stubGlobal('sessionStorage', storage);

    expect(() => markPhoneChangedNotice()).not.toThrow();
    expect(consumePhoneChangedNotice()).toBe(false);
  });

  it('consumes a saved notice once', () => {
    const storage = {
      getItem: vi.fn(() => '1'),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };
    vi.stubGlobal('sessionStorage', storage);

    expect(consumePhoneChangedNotice()).toBe(true);
    expect(storage.removeItem).toHaveBeenCalledWith('baladiguard-phone-changed');
  });
});

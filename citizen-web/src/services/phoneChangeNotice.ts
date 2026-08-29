const PHONE_CHANGED_KEY = 'baladiguard-phone-changed';

/**
 * Storage is only used to show a one-time confirmation after phone changes.
 * Authentication state must never depend on it because browsers can block
 * session storage in privacy-restricted contexts.
 */
export function markPhoneChangedNotice(): void {
  try {
    window.sessionStorage.setItem(PHONE_CHANGED_KEY, '1');
  } catch {
    // The confirmation remains optional when storage is unavailable.
  }
}

export function consumePhoneChangedNotice(): boolean {
  try {
    const changed = window.sessionStorage.getItem(PHONE_CHANGED_KEY) === '1';
    if (changed) window.sessionStorage.removeItem(PHONE_CHANGED_KEY);
    return changed;
  } catch {
    return false;
  }
}

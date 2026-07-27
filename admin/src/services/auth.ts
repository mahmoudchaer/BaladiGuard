import { config } from '@/services/config';

const STAFF_SESSION_KEY = 'baladiguard.staffSession';

export type StaffSession = {
  username: string;
  signedInAt: string;
};

export type LoginResult =
  | {
      ok: true;
      session: StaffSession;
    }
  | {
      ok: false;
      error: string;
    };

function getBrowserStorage(): Storage | null {
  let storage: Storage;

  try {
    storage = window.localStorage;
  } catch {
    return null;
  }

  if (
    typeof storage?.getItem !== 'function' ||
    typeof storage?.setItem !== 'function' ||
    typeof storage?.removeItem !== 'function'
  ) {
    return null;
  }

  return storage;
}

export function getStoredStaffSession(): StaffSession | null {
  const storage = getBrowserStorage();
  let storedSession: string | null | undefined;

  try {
    storedSession = storage?.getItem(STAFF_SESSION_KEY);
  } catch {
    return null;
  }

  if (!storedSession) {
    return null;
  }

  try {
    const session = JSON.parse(storedSession) as Partial<StaffSession>;

    if (typeof session.username !== 'string' || typeof session.signedInAt !== 'string') {
      try {
        storage?.removeItem(STAFF_SESSION_KEY);
      } catch {
        return null;
      }
      return null;
    }

    return {
      username: session.username,
      signedInAt: session.signedInAt,
    };
  } catch {
    try {
      storage?.removeItem(STAFF_SESSION_KEY);
    } catch {
      return null;
    }
    return null;
  }
}

export function loginStaff(username: string, password: string): LoginResult {
  const trimmedUsername = username.trim();

  if (trimmedUsername !== config.staffAuth.username || password !== config.staffAuth.password) {
    return {
      ok: false,
      error: 'Invalid staff username or password.',
    };
  }

  const session: StaffSession = {
    username: trimmedUsername,
    signedInAt: new Date().toISOString(),
  };
  const storage = getBrowserStorage();

  if (!storage) {
    return {
      ok: false,
      error: 'Unable to create a staff session in this browser.',
    };
  }

  try {
    storage.setItem(STAFF_SESSION_KEY, JSON.stringify(session));
  } catch {
    return {
      ok: false,
      error: 'Unable to create a staff session in this browser.',
    };
  }

  return {
    ok: true,
    session,
  };
}

export function logoutStaff() {
  try {
    getBrowserStorage()?.removeItem(STAFF_SESSION_KEY);
  } catch {
    return;
  }
}

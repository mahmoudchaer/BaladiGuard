import { config } from '@/services/config';

const STAFF_SESSION_KEY = 'baladiguard.staffSession';

export type StaffSession = {
  username: string;
  signedInAt: string;
  /** Backend-issued Bearer token for staff API calls (issue #72). */
  accessToken: string;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
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

    if (
      typeof session.username !== 'string' ||
      typeof session.signedInAt !== 'string' ||
      typeof session.accessToken !== 'string' ||
      session.accessToken.trim().length === 0
    ) {
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
      accessToken: session.accessToken,
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

function storeSession(session: StaffSession): LoginResult {
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

async function loginStaffAgainstApi(username: string, password: string): Promise<LoginResult> {
  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}/v1/staff/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    return {
      ok: false,
      error: 'Unable to reach the staff authentication service.',
    };
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const message =
      isRecord(errorBody) &&
      isRecord(errorBody.error) &&
      typeof errorBody.error.message === 'string'
        ? errorBody.error.message
        : 'Invalid staff username or password.';
    return {
      ok: false,
      error: message,
    };
  }

  const body: unknown = await response.json().catch(() => null);
  if (
    !isRecord(body) ||
    typeof body.accessToken !== 'string' ||
    typeof body.username !== 'string'
  ) {
    return {
      ok: false,
      error: 'Unexpected staff authentication response.',
    };
  }

  return storeSession({
    username: body.username,
    signedInAt: new Date().toISOString(),
    accessToken: body.accessToken,
  });
}

function loginStaffAgainstMock(username: string, password: string): LoginResult {
  const trimmedUsername = username.trim();

  if (trimmedUsername !== config.staffAuth.username || password !== config.staffAuth.password) {
    return {
      ok: false,
      error: 'Invalid staff username or password.',
    };
  }

  // Mock mode never talks to the API; issue a local placeholder token so the
  // session shape matches the real backend contract.
  return storeSession({
    username: trimmedUsername,
    signedInAt: new Date().toISOString(),
    accessToken: `mock-staff-token:${trimmedUsername}`,
  });
}

export async function loginStaff(username: string, password: string): Promise<LoginResult> {
  if (config.useMockData) {
    return loginStaffAgainstMock(username, password);
  }

  return loginStaffAgainstApi(username, password);
}

export function logoutStaff() {
  try {
    getBrowserStorage()?.removeItem(STAFF_SESSION_KEY);
  } catch {
    return;
  }
}

/** Authorization headers for staff-only API calls (issue #72). */
export function getStaffAuthHeaders(): Record<string, string> {
  const session = getStoredStaffSession();
  if (!session?.accessToken) {
    return {};
  }
  return {
    Authorization: `Bearer ${session.accessToken}`,
  };
}

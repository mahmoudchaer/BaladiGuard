import { config } from '@/services/config';

const STAFF_SESSION_KEY = 'baladiguard.staffSession';

export type StaffRole = 'municipal_staff' | 'administrator';

export type StaffSession = {
  username: string;
  name: string;
  staffId: string;
  role: StaffRole;
  municipalityId: string | null;
  departmentIds: string[] | null;
  signedInAt: string;
  /** Backend-issued Bearer token for staff API calls. */
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

function isStaffRole(value: unknown): value is StaffRole {
  return value === 'municipal_staff' || value === 'administrator';
}

function parseDepartmentIds(value: unknown): string[] | null {
  if (value === null) {
    return null;
  }
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) {
    return null;
  }
  return value;
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
    const departmentIds =
      session.departmentIds === undefined ? null : parseDepartmentIds(session.departmentIds);

    if (
      typeof session.username !== 'string' ||
      typeof session.name !== 'string' ||
      typeof session.staffId !== 'string' ||
      !isStaffRole(session.role) ||
      (session.municipalityId !== null && typeof session.municipalityId !== 'string') ||
      (session.departmentIds !== undefined &&
        session.departmentIds !== null &&
        departmentIds === null) ||
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
      name: session.name,
      staffId: session.staffId,
      role: session.role,
      municipalityId: session.municipalityId ?? null,
      departmentIds,
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

function roleLabel(role: StaffRole): string {
  return role === 'administrator' ? 'Administrator' : 'Municipal staff';
}

export function getStaffRoleLabel(role: StaffRole | undefined): string {
  if (!role) {
    return 'Staff';
  }
  return roleLabel(role);
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
    typeof body.username !== 'string' ||
    typeof body.name !== 'string' ||
    typeof body.staffId !== 'string' ||
    !isStaffRole(body.role)
  ) {
    return {
      ok: false,
      error: 'Unexpected staff authentication response.',
    };
  }

  const municipalityId =
    body.municipalityId === null || typeof body.municipalityId === 'string'
      ? body.municipalityId
      : null;
  const departmentIds =
    body.departmentIds === undefined ? null : parseDepartmentIds(body.departmentIds);
  if (body.departmentIds !== undefined && body.departmentIds !== null && departmentIds === null) {
    return {
      ok: false,
      error: 'Unexpected staff authentication response.',
    };
  }

  return storeSession({
    username: body.username,
    name: body.name,
    staffId: body.staffId,
    role: body.role,
    municipalityId,
    departmentIds,
    signedInAt: new Date().toISOString(),
    accessToken: body.accessToken,
  });
}

function loginStaffAgainstMock(username: string, password: string): LoginResult {
  const trimmedUsername = username.trim().toLowerCase();

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
    name: 'Mock Municipal Staff',
    staffId: 'staff_mock_001',
    role: 'municipal_staff',
    municipalityId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    departmentIds: ['d1111111-1111-1111-1111-111111111111'],
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

export async function logoutStaff(): Promise<void> {
  const session = getStoredStaffSession();
  try {
    getBrowserStorage()?.removeItem(STAFF_SESSION_KEY);
  } catch {
    // Continue; local clear failure should not block navigation.
  }

  if (!session?.accessToken || config.useMockData) {
    return;
  }

  try {
    await fetch(`${config.apiBaseUrl}/v1/staff/logout`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });
  } catch {
    // Best-effort server revoke; local session is already cleared.
  }
}

/** Authorization headers for staff-only API calls. */
export function getStaffAuthHeaders(): Record<string, string> {
  const session = getStoredStaffSession();
  if (!session?.accessToken) {
    return {};
  }
  return {
    Authorization: `Bearer ${session.accessToken}`,
  };
}

export type PasswordResetResult =
  | { ok: true; message: string }
  | { ok: false; error: string };

function apiErrorMessage(errorBody: unknown, fallback: string): string {
  if (
    isRecord(errorBody) &&
    isRecord(errorBody.error) &&
    typeof errorBody.error.message === 'string'
  ) {
    return errorBody.error.message;
  }
  return fallback;
}

export async function requestStaffPasswordReset(username: string): Promise<PasswordResetResult> {
  if (config.useMockData) {
    return {
      ok: true,
      message:
        'If a matching staff account exists, a password reset code has been issued. (Mock mode — use the live API for real recovery.)',
    };
  }

  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}/v1/staff/password-reset/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim() }),
    });
  } catch {
    return { ok: false, error: 'Unable to reach the staff authentication service.' };
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    return { ok: false, error: apiErrorMessage(body, 'Unable to request a password reset.') };
  }
  if (!isRecord(body) || typeof body.message !== 'string') {
    return { ok: false, error: 'Unexpected password reset response.' };
  }
  return { ok: true, message: body.message };
}

export async function confirmStaffPasswordReset(input: {
  username: string;
  code: string;
  newPassword: string;
}): Promise<PasswordResetResult> {
  if (config.useMockData) {
    return {
      ok: false,
      error: 'Password reset requires the live staff API. Disable mock data to continue.',
    };
  }

  let response: Response;
  try {
    response = await fetch(`${config.apiBaseUrl}/v1/staff/password-reset/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: input.username.trim(),
        code: input.code.trim(),
        newPassword: input.newPassword,
      }),
    });
  } catch {
    return { ok: false, error: 'Unable to reach the staff authentication service.' };
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    return { ok: false, error: apiErrorMessage(body, 'Unable to reset the password.') };
  }
  if (!isRecord(body) || typeof body.message !== 'string') {
    return { ok: false, error: 'Unexpected password reset response.' };
  }
  return { ok: true, message: body.message };
}

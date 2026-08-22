import type {
  CitizenDeleteResponse,
  CitizenOtpRequestPayload,
  CitizenOtpRequestResponse,
  CitizenOtpVerifyPayload,
  CitizenOtpVerifyResponse,
  CitizenProfile,
  CitizenProfileUpdatePayload,
  LegalAcceptanceRequest,
} from '@/types/citizen';
import { appConfig } from '@/services/config';
import { getAuthHeaders, parseApiError, parseApiErrorCode } from '@/services/api/http';

export const OTP_NETWORK_MESSAGE =
  'Unable to reach the server. Check your connection and try again.';
export const OTP_GENERIC_ERROR_MESSAGE = 'Something went wrong. Please try again.';
export const OTP_INVALID_MESSAGE = 'The verification code is incorrect.';
export const OTP_EXPIRED_MESSAGE = 'The verification challenge is no longer valid.';
export const OTP_RATE_LIMITED_MESSAGE = 'Too many attempts. Please wait before trying again.';
export const ACCOUNT_INACTIVE_MESSAGE = 'This account is inactive and cannot sign in.';
export const SESSION_UNAUTHORIZED_MESSAGE = 'Your session has expired. Please sign in again.';
export const PHONE_UNAVAILABLE_MESSAGE = 'This phone number is already linked to another account.';
export const PROFILE_UPDATE_SUCCESS_MESSAGE = 'Your profile was updated.';

export class CitizenAuthApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryAfterSeconds: number | null;

  constructor(
    message: string,
    options: { code: string; status: number; retryAfterSeconds?: number | null },
  ) {
    super(message);
    this.name = 'CitizenAuthApiError';
    this.code = options.code;
    this.status = options.status;
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
  }
}

function isOfflineError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  const message = error.message.toLowerCase();
  return (
    error.name === 'TypeError' ||
    message.includes('network') ||
    message.includes('failed to fetch') ||
    message.includes('network request failed')
  );
}

function readRetryAfter(response: Response): number | null {
  const header = response.headers?.get?.('Retry-After');
  if (!header) {
    return null;
  }
  const seconds = Number.parseInt(header, 10);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

async function throwMappedAuthError(response: Response, fallbackMessage: string): Promise<never> {
  const code = (await parseApiErrorCode(response.clone())) ?? 'UNKNOWN';
  const message = await parseApiError(response, fallbackMessage);
  const retryAfterSeconds = readRetryAfter(response);

  if (response.status === 429 || code === 'RATE_LIMITED' || code === 'RATE_LIMIT_EXCEEDED') {
    throw new CitizenAuthApiError(message || OTP_RATE_LIMITED_MESSAGE, {
      code: 'RATE_LIMITED',
      status: 429,
      retryAfterSeconds,
    });
  }

  if (code === 'INVALID_OTP') {
    throw new CitizenAuthApiError(OTP_INVALID_MESSAGE, {
      code,
      status: response.status,
      retryAfterSeconds,
    });
  }

  if (code === 'OTP_EXPIRED') {
    throw new CitizenAuthApiError(OTP_EXPIRED_MESSAGE, {
      code,
      status: response.status,
      retryAfterSeconds,
    });
  }

  if (code === 'ACCOUNT_INACTIVE') {
    throw new CitizenAuthApiError(ACCOUNT_INACTIVE_MESSAGE, {
      code,
      status: response.status,
      retryAfterSeconds,
    });
  }

  if (response.status === 401 || code === 'UNAUTHORIZED') {
    throw new CitizenAuthApiError(SESSION_UNAUTHORIZED_MESSAGE, {
      code: 'UNAUTHORIZED',
      status: 401,
      retryAfterSeconds,
    });
  }

  if (code === 'PHONE_UNAVAILABLE') {
    throw new CitizenAuthApiError(PHONE_UNAVAILABLE_MESSAGE, {
      code: 'PHONE_UNAVAILABLE',
      status: response.status || 409,
      retryAfterSeconds,
    });
  }

  if (code === 'LEGAL_ACCEPTANCE_REQUIRED') {
    throw new CitizenAuthApiError(message || 'Legal acceptance is required.', {
      code: 'LEGAL_ACCEPTANCE_REQUIRED',
      status: response.status || 400,
      retryAfterSeconds,
    });
  }

  throw new CitizenAuthApiError(message || OTP_GENERIC_ERROR_MESSAGE, {
    code,
    status: response.status,
    retryAfterSeconds,
  });
}

async function citizenFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${appConfig.apiBaseUrl}${path}`, init);
  } catch (error) {
    if (isOfflineError(error)) {
      throw new CitizenAuthApiError(OTP_NETWORK_MESSAGE, {
        code: 'NETWORK_ERROR',
        status: 0,
      });
    }
    throw new CitizenAuthApiError(OTP_GENERIC_ERROR_MESSAGE, {
      code: 'UNKNOWN',
      status: 0,
    });
  }
}

export async function requestCitizenOtp(
  payload: CitizenOtpRequestPayload,
): Promise<CitizenOtpRequestResponse> {
  const body: CitizenOtpRequestPayload = {
    phone: payload.phone,
    purpose: payload.purpose ?? 'LOGIN_OR_SIGNUP',
  };
  if (payload.region) {
    body.region = payload.region;
  }

  const response = await citizenFetch('/citizen/auth/otp/request', {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenOtpRequestResponse>;
}

export async function verifyCitizenOtp(
  payload: CitizenOtpVerifyPayload,
): Promise<CitizenOtpVerifyResponse> {
  const body: Record<string, unknown> = {
    challengeId: payload.challengeId,
    code: payload.code,
  };
  if (payload.fullName?.trim()) {
    body.fullName = payload.fullName.trim();
  }
  if (payload.acceptLegal !== undefined) {
    body.acceptLegal = payload.acceptLegal;
  }
  if (payload.legalLocale) {
    body.legalLocale = payload.legalLocale;
  }

  const response = await citizenFetch('/citizen/auth/otp/verify', {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenOtpVerifyResponse>;
}

export async function logoutCitizen(accessToken: string): Promise<void> {
  const response = await citizenFetch('/citizen/auth/logout', {
    method: 'POST',
    headers: getAuthHeaders(accessToken),
  });

  if (response.status === 204) {
    return;
  }

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }
}

export async function getCitizenMe(accessToken: string): Promise<CitizenProfile> {
  const response = await citizenFetch('/citizen/me', {
    method: 'GET',
    headers: getAuthHeaders(accessToken),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenProfile>;
}

function buildProfilePatchBody(patch: CitizenProfileUpdatePayload): Record<string, unknown> {
  const body: Record<string, unknown> = {};

  if (patch.fullName !== undefined) {
    body.fullName = patch.fullName === null ? null : patch.fullName.trim();
  }
  if (patch.email !== undefined) {
    body.email = patch.email === null ? null : patch.email.trim() || null;
  }
  if (patch.notificationPreferences !== undefined) {
    body.notificationPreferences = patch.notificationPreferences;
  }
  if (patch.publicNameVisible !== undefined) {
    body.publicNameVisible = patch.publicNameVisible;
  }
  if (patch.phone !== undefined) {
    body.phone = patch.phone;
  }
  if (patch.region !== undefined) {
    body.region = patch.region;
  }
  if (patch.phoneChangeChallengeId !== undefined) {
    body.phoneChangeChallengeId = patch.phoneChangeChallengeId;
  }
  if (patch.phoneChangeCode !== undefined) {
    body.phoneChangeCode = patch.phoneChangeCode;
  }

  return body;
}

export async function updateCitizenProfile(
  accessToken: string,
  patch: CitizenProfileUpdatePayload,
): Promise<CitizenProfile> {
  const response = await citizenFetch('/citizen/me', {
    method: 'PATCH',
    headers: {
      ...getAuthHeaders(accessToken),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(buildProfilePatchBody(patch)),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenProfile>;
}

export function profileFromVerifyResponse(response: CitizenOtpVerifyResponse): CitizenProfile {
  return {
    userId: response.userId,
    phone: response.phone,
    phoneVerifiedAt: response.phoneVerifiedAt,
    fullName: response.fullName,
    email: response.email,
    notificationPreferences: response.notificationPreferences,
    publicNameVisible: response.publicNameVisible,
    active: response.active,
    contributionReady: response.contributionReady,
    legalAcceptance: response.legalAcceptance ?? null,
    legalAcceptanceRequired: response.legalAcceptanceRequired ?? false,
    createdAt: response.createdAt,
    updatedAt: response.updatedAt,
  };
}

export async function acceptCitizenLegal(
  accessToken: string,
  payload: LegalAcceptanceRequest,
): Promise<CitizenProfile> {
  const response = await citizenFetch('/citizen/me/legal-acceptance', {
    method: 'POST',
    headers: {
      ...getAuthHeaders(accessToken),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenProfile>;
}

export async function exportCitizenMe(accessToken: string): Promise<unknown> {
  const response = await citizenFetch('/citizen/me/export', {
    method: 'GET',
    headers: getAuthHeaders(accessToken),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json();
}

export async function deleteCitizenMe(accessToken: string): Promise<CitizenDeleteResponse> {
  const response = await citizenFetch('/citizen/me/delete', {
    method: 'POST',
    headers: {
      ...getAuthHeaders(accessToken),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    await throwMappedAuthError(response, OTP_GENERIC_ERROR_MESSAGE);
  }

  return response.json() as Promise<CitizenDeleteResponse>;
}

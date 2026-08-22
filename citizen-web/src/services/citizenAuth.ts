import { apiError, apiFetch, jsonRequest } from '@/services/api';
import type {
  CitizenDeleteResponse,
  CitizenProfile,
  CitizenProfilePatch,
  LegalAcceptanceRequest,
  OtpChallenge,
  OtpVerifyOptions,
} from '@/types/citizen';

export async function requestOtp(
  phone: string,
  region: string,
  purpose: 'LOGIN_OR_SIGNUP' | 'CHANGE_PHONE' = 'LOGIN_OR_SIGNUP',
): Promise<OtpChallenge> {
  return jsonRequest(
    '/citizen/auth/otp/request',
    { method: 'POST', body: JSON.stringify({ phone, region, purpose }) },
    'Unable to send a verification code right now.',
  );
}

export async function verifyOtp(
  challengeId: string,
  code: string,
  options: OtpVerifyOptions,
): Promise<CitizenProfile> {
  const body: Record<string, unknown> = {
    challengeId,
    code,
    acceptLegal: options.acceptLegal,
  };
  if (options.legalLocale) {
    body.legalLocale = options.legalLocale;
  }
  return jsonRequest(
    '/citizen/auth/otp/verify',
    {
      method: 'POST',
      headers: { 'X-Citizen-Session-Mode': 'cookie' },
      body: JSON.stringify(body),
    },
    'Unable to verify that code.',
  );
}

export async function getMe(): Promise<CitizenProfile> {
  return jsonRequest('/citizen/me', { method: 'GET' }, 'Unable to restore your session.');
}

export async function updateMe(patch: CitizenProfilePatch): Promise<CitizenProfile> {
  return jsonRequest(
    '/citizen/me',
    { method: 'PATCH', body: JSON.stringify(patch) },
    'Unable to update your profile.',
  );
}

export async function acceptLegal(payload: LegalAcceptanceRequest): Promise<CitizenProfile> {
  return jsonRequest(
    '/citizen/me/legal-acceptance',
    { method: 'POST', body: JSON.stringify(payload) },
    'Unable to record legal acceptance.',
  );
}

export async function exportMe(): Promise<unknown> {
  return jsonRequest('/citizen/me/export', { method: 'GET' }, 'Unable to export your data.');
}

export async function deleteMe(): Promise<CitizenDeleteResponse> {
  return jsonRequest(
    '/citizen/me/delete',
    { method: 'POST', body: JSON.stringify({}) },
    'Unable to delete your account.',
  );
}

export async function logout(): Promise<void> {
  const response = await apiFetch('/citizen/auth/logout', { method: 'POST' });
  if (response.status !== 204 && !response.ok) {
    throw await apiError(response, 'Unable to sign out on the server.');
  }
}

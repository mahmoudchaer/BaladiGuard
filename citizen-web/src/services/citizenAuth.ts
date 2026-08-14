import { apiError, apiFetch, jsonRequest } from '@/services/api';
import type { CitizenProfile, CitizenProfilePatch, OtpChallenge } from '@/types/citizen';

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

export async function verifyOtp(challengeId: string, code: string): Promise<CitizenProfile> {
  return jsonRequest(
    '/citizen/auth/otp/verify',
    {
      method: 'POST',
      headers: { 'X-Citizen-Session-Mode': 'cookie' },
      body: JSON.stringify({ challengeId, code }),
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

export async function logout(): Promise<void> {
  const response = await apiFetch('/citizen/auth/logout', { method: 'POST' });
  if (response.status !== 204 && !response.ok) {
    throw await apiError(response, 'Unable to sign out on the server.');
  }
}

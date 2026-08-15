import { apiError, apiFetch, jsonRequest } from '@/services/api';
import type {
  CitizenTicketHistoryResponse,
  ResolutionFeedbackStatus,
  SubmitTicketResponse,
} from '@/types/ticket';

export type ValidatedLocation = {
  latitude: number;
  longitude: number;
  addressText: string;
  source: 'GPS' | 'MANUAL' | 'PLACEHOLDER';
};

export async function validateLocation(input: {
  addressText?: string;
  latitude?: number;
  longitude?: number;
}): Promise<ValidatedLocation> {
  const result = await jsonRequest<{ success: boolean; location: ValidatedLocation | null }>(
    '/locations/validate',
    { method: 'POST', body: JSON.stringify(input) },
    'We could not validate that location.',
  );
  if (!result.location) throw new Error('Choose a location inside the supported service area.');
  return result.location;
}

export async function uploadPhoto(file: File): Promise<string> {
  const data = new FormData();
  data.append('file', file, file.name);
  const response = await apiFetch('/uploads/report-photo', { method: 'POST', body: data });
  if (!response.ok) throw await apiError(response, 'Unable to upload that photo.');
  const result = (await response.json()) as { imageObjectKey?: string };
  if (!result.imageObjectKey)
    throw new Error('The upload completed without a safe photo reference.');
  return result.imageObjectKey;
}

export async function createTicket(input: {
  description: string;
  location: ValidatedLocation;
  imageObjectKey: string;
  clientSubmissionId: string;
}): Promise<SubmitTicketResponse> {
  return jsonRequest(
    '/tickets',
    {
      method: 'POST',
      headers: { 'Idempotency-Key': input.clientSubmissionId },
      body: JSON.stringify({
        description: input.description,
        languageHint: 'auto',
        location: input.location,
        imageObjectKey: input.imageObjectKey,
        clientSubmissionId: input.clientSubmissionId,
        clientMetadata: { platform: 'web', appVersion: '0.1.0' },
      }),
    },
    'Unable to submit your report.',
  );
}

export async function getHistory(
  limit = 20,
  cursor?: string | null,
): Promise<CitizenTicketHistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) params.set('cursor', cursor);
  return jsonRequest(
    `/citizen/me/tickets?${params}`,
    { method: 'GET' },
    'Unable to load your reports.',
  );
}

export async function submitResolutionFeedback(
  trackingCode: string,
  status: ResolutionFeedbackStatus,
  note?: string,
): Promise<{
  canSubmit: boolean;
  status: ResolutionFeedbackStatus | null;
}> {
  return jsonRequest(
    `/citizen/me/tickets/${encodeURIComponent(trackingCode)}/resolution-feedback`,
    {
      method: 'POST',
      body: JSON.stringify({ status, note }),
    },
    'Unable to submit resolution feedback.',
  );
}

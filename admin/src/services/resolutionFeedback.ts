import { config } from '@/services/config';
import { getStaffAuthHeaders } from '@/services/auth';
import type {
  ResolutionFeedbackReviewAction,
  StaffResolutionFeedback,
} from '@/types/resolutionFeedback';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

async function throwApiError(response: Response, fallbackMessage: string): Promise<never> {
  const body = await response.json().catch(() => null);
  const error = isRecord(body) && isRecord(body.error) ? body.error : null;
  const message = error && typeof error.message === 'string' ? error.message : fallbackMessage;
  throw new Error(message);
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null;
}

function normalizeFeedback(data: unknown): StaffResolutionFeedback {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    throw new Error('Unexpected resolution-feedback response shape.');
  }
  return {
    ticketId: data.ticketId,
    trackingCode: asString(data.trackingCode) ?? '',
    ticketStatus: asString(data.ticketStatus) ?? '',
    status:
      data.status === 'CONFIRMED_FIXED' || data.status === 'STILL_UNRESOLVED' ? data.status : null,
    note: asString(data.note),
    submittedAt: asString(data.submittedAt),
    reviewStatus:
      data.reviewStatus === 'PENDING' || data.reviewStatus === 'REVIEWED'
        ? data.reviewStatus
        : null,
    reviewedAt: asString(data.reviewedAt),
    reviewedBy: asString(data.reviewedBy),
    reviewAction:
      data.reviewAction === 'KEEP_RESOLVED' || data.reviewAction === 'RETURN_IN_PROGRESS'
        ? data.reviewAction
        : null,
    needsReview: data.needsReview === true,
  };
}

export async function fetchResolutionFeedback(ticketId: string): Promise<StaffResolutionFeedback> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/resolution-feedback`,
    { headers: { ...getStaffAuthHeaders() } },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to load resolution feedback.');
  }
  return normalizeFeedback(await response.json());
}

export async function reviewResolutionFeedback(
  ticketId: string,
  action: ResolutionFeedbackReviewAction,
): Promise<StaffResolutionFeedback> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/resolution-feedback/review`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify({ action }),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to review resolution feedback.');
  }
  return normalizeFeedback(await response.json());
}

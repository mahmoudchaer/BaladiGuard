import { Platform } from 'react-native';

import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type {
  CitizenTicketHistoryResponse,
  CitizenTicketResponse,
  PublicTicketListResponse,
  PublicTicketResponse,
  SubmitTicketRequest,
  SubmitTicketResponse,
} from '@/types/ticket';
import { appConfig } from '@/services/config';
import { getAuthHeaders, handleUnauthorizedResponse, parseApiError } from '@/services/api/http';
import {
  getCitizenTicketHistoryMock,
  getPublicTicketByNumberMock,
  getPublicTicketsMock,
  getTicketByTrackingCodeMock,
  submitTicketMock,
} from '@/services/api/mockTickets';
import { createClientSubmissionId } from '@/services/reportDraft';
import { uploadReportPhoto } from '@/services/api/uploads';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export type SubmitReportPhase = 'uploading-photo' | 'submitting-report';

export type SubmitReportPartialState = {
  clientSubmissionId: string;
  imageObjectKey?: string;
};

export class SubmitReportError extends Error {
  readonly code: 'offline' | 'upload' | 'submit' | 'photo_missing' | 'validation' | 'unknown';
  readonly imageObjectKey?: string;
  readonly clientSubmissionId?: string;
  readonly photoUploaded: boolean;

  constructor(
    message: string,
    options: {
      code: SubmitReportError['code'];
      imageObjectKey?: string;
      clientSubmissionId?: string;
      photoUploaded?: boolean;
    },
  ) {
    super(message);
    this.name = 'SubmitReportError';
    this.code = options.code;
    this.imageObjectKey = options.imageObjectKey;
    this.clientSubmissionId = options.clientSubmissionId;
    this.photoUploaded = options.photoUploaded ?? Boolean(options.imageObjectKey);
  }
}

export const TRACK_LOOKUP_NOT_FOUND_MESSAGE =
  "We couldn't find a report with that tracking code. Check the code and try again.";
export const TRACK_LOOKUP_INVALID_MESSAGE =
  'That tracking code is not valid. Use the 6-character code from your submission confirmation.';
export const TRACK_LOOKUP_NETWORK_MESSAGE =
  'Unable to look up that report right now. Please try again.';
export const TICKET_HISTORY_NETWORK_MESSAGE =
  'Unable to load your report history right now. Check your connection and try again.';
export const TICKET_HISTORY_UNAUTHORIZED_MESSAGE =
  'Your session has expired. Please sign in again.';
export const PUBLIC_TICKETS_NETWORK_MESSAGE =
  'Unable to load public reports right now. Check your connection and try again.';

type CitizenTicketHistoryOptions = {
  accessToken: string;
  limit?: number;
  cursor?: string | null;
};

type SubmitReportOptions = {
  onProgress?: (phase: SubmitReportPhase) => void;
  /** Reuse after a prior partial failure so retries stay idempotent. */
  clientSubmissionId?: string;
  /** Safe server artifact from a successful photo upload on a previous attempt. */
  imageObjectKey?: string;
  onPartialState?: (state: SubmitReportPartialState) => void;
};

type PublicTicketListOptions = {
  limit?: number;
  cursor?: string | null;
  signal?: AbortSignal;
};

const buildSubmitPayload = (
  values: ReportFormValues,
  imageObjectKey: string,
  clientSubmissionId?: string,
): SubmitTicketRequest => {
  return {
    description: values.description.trim(),
    languageHint: 'auto',
    location: {
      latitude: values.latitude as number,
      longitude: values.longitude as number,
      addressText: values.addressText.trim(),
      source: values.locationSource,
    },
    imageObjectKey,
    clientMetadata: {
      platform: Platform.OS,
      appVersion: appConfig.appVersion,
    },
    ...(clientSubmissionId ? { clientSubmissionId } : {}),
  };
};

const toReportPhoto = (values: ReportFormValues) => ({
  uri: values.photoUri,
  fileName: values.photoFileName?.trim() || `photo-${Date.now()}.jpg`,
  contentType: values.photoContentType?.trim() || 'image/jpeg',
});

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

export async function submitReport(
  values: ReportFormValues,
  options?: SubmitReportOptions,
): Promise<SubmitTicketResponse> {
  const clientSubmissionId = options?.clientSubmissionId?.trim() || createClientSubmissionId();

  const notifyPartial = (imageObjectKey?: string) => {
    options?.onPartialState?.({
      clientSubmissionId,
      imageObjectKey,
    });
  };

  if (appConfig.enableMockApi) {
    const payload = buildSubmitPayload(
      values,
      options?.imageObjectKey ||
        (values.photoFileName ? `reports/mock/${values.photoFileName}` : 'reports/mock/photo.jpg'),
      clientSubmissionId,
    );
    return submitTicketMock(payload);
  }

  let imageObjectKey = options?.imageObjectKey?.trim() || undefined;

  try {
    if (!imageObjectKey) {
      if (!values.photoUri?.trim()) {
        throw new SubmitReportError(
          'Your photo is no longer available on this device. Choose a photo again, then retry.',
          { code: 'photo_missing', clientSubmissionId },
        );
      }
      options?.onProgress?.('uploading-photo');
      try {
        imageObjectKey = await uploadReportPhoto(toReportPhoto(values));
      } catch (error) {
        if (isOfflineError(error)) {
          throw new SubmitReportError(
            'You appear to be offline. Your draft is saved on this device — reconnect and try again.',
            { code: 'offline', clientSubmissionId },
          );
        }
        const message =
          error instanceof Error ? error.message : 'Unable to upload your photo right now.';
        throw new SubmitReportError(
          `${message} Your draft is still on this device. Check the photo and try again.`,
          { code: 'upload', clientSubmissionId },
        );
      }
      notifyPartial(imageObjectKey);
    } else {
      notifyPartial(imageObjectKey);
    }

    options?.onProgress?.('submitting-report');
    const payload = buildSubmitPayload(values, imageObjectKey, clientSubmissionId);

    let response: Response;
    try {
      response = await fetch(`${appConfig.apiBaseUrl}/tickets`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
          'Idempotency-Key': clientSubmissionId,
        },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      if (isOfflineError(error)) {
        throw new SubmitReportError(
          'Network lost after the photo step. Your draft and uploaded photo reference are saved — retry when online (no duplicate report).',
          {
            code: 'offline',
            clientSubmissionId,
            imageObjectKey,
            photoUploaded: true,
          },
        );
      }
      throw new SubmitReportError(
        'Unable to reach the server to save your report. Your draft is kept — please try again.',
        {
          code: 'submit',
          clientSubmissionId,
          imageObjectKey,
          photoUploaded: true,
        },
      );
    }

    if (!response.ok) {
      handleUnauthorizedResponse(response.status);
      const message = await parseApiError(response, 'Unable to submit your report right now.');
      throw new SubmitReportError(
        `Your photo was uploaded, but the report could not be saved. ${message} Retry will not create a duplicate.`,
        {
          code: 'submit',
          clientSubmissionId,
          imageObjectKey,
          photoUploaded: true,
        },
      );
    }

    return response.json() as Promise<SubmitTicketResponse>;
  } catch (error) {
    if (error instanceof SubmitReportError) {
      throw error;
    }
    if (isOfflineError(error)) {
      throw new SubmitReportError(
        'You appear to be offline. Your draft is saved on this device — reconnect and try again.',
        {
          code: 'offline',
          clientSubmissionId,
          imageObjectKey,
          photoUploaded: Boolean(imageObjectKey),
        },
      );
    }
    const message =
      error instanceof Error ? error.message : 'Something went wrong. Please try again.';
    throw new SubmitReportError(message, {
      code: 'unknown',
      clientSubmissionId,
      imageObjectKey,
      photoUploaded: Boolean(imageObjectKey),
    });
  }
}

/**
 * Public citizen tracking lookup via GET /v1/tickets/track/{trackingCode}.
 * Callers should validate client-side first; this still rejects invalid codes
 * without contacting the API.
 */
export async function getTicketByTrackingCode(
  trackingCode: string,
): Promise<CitizenTicketResponse> {
  const normalized = normalizeTrackingCode(trackingCode);
  if (!isValidTrackingCode(normalized)) {
    throw new Error(TRACK_LOOKUP_INVALID_MESSAGE);
  }

  if (appConfig.enableMockApi) {
    return getTicketByTrackingCodeMock(normalized);
  }

  const response = await fetch(
    `${appConfig.apiBaseUrl}/tickets/track/${encodeURIComponent(normalized)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  );

  if (response.status === 404) {
    // Fixed copy only — never surface server details that could leak ticket existence nuances.
    throw new Error(TRACK_LOOKUP_NOT_FOUND_MESSAGE);
  }

  if (response.status === 400) {
    throw new Error(TRACK_LOOKUP_INVALID_MESSAGE);
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response, TRACK_LOOKUP_NETWORK_MESSAGE));
  }

  return response.json() as Promise<CitizenTicketResponse>;
}

export async function getCitizenTicketHistory({
  accessToken,
  limit = 20,
  cursor,
}: CitizenTicketHistoryOptions): Promise<CitizenTicketHistoryResponse> {
  if (appConfig.enableMockApi) {
    return getCitizenTicketHistoryMock();
  }

  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set('cursor', cursor);
  }

  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}/citizen/me/tickets?${params.toString()}`, {
      method: 'GET',
      headers: getAuthHeaders(accessToken),
    });
  } catch (error) {
    if (isOfflineError(error)) {
      throw new Error(TICKET_HISTORY_NETWORK_MESSAGE);
    }
    throw error;
  }

  if (response.status === 401) {
    handleUnauthorizedResponse(response.status);
    throw new Error(TICKET_HISTORY_UNAUTHORIZED_MESSAGE);
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response, TICKET_HISTORY_NETWORK_MESSAGE));
  }

  return response.json() as Promise<CitizenTicketHistoryResponse>;
}

export async function getPublicTickets({
  limit = 20,
  cursor,
  signal,
}: PublicTicketListOptions = {}): Promise<PublicTicketListResponse> {
  if (appConfig.enableMockApi) {
    return getPublicTicketsMock({ limit });
  }

  const params = new URLSearchParams({ limit: String(limit) });
  if (cursor) {
    params.set('cursor', cursor);
  }

  let response: Response;
  try {
    response = await fetch(`${appConfig.apiBaseUrl}/tickets/public?${params.toString()}`, {
      method: 'GET',
      headers: getAuthHeaders(),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) {
      throw error;
    }
    if (isOfflineError(error)) {
      throw new Error(PUBLIC_TICKETS_NETWORK_MESSAGE);
    }
    throw error;
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response, PUBLIC_TICKETS_NETWORK_MESSAGE));
  }

  return response.json() as Promise<PublicTicketListResponse>;
}

export async function getPublicTicketByNumber(ticketNumber: string): Promise<PublicTicketResponse> {
  const normalized = ticketNumber.trim().toUpperCase();

  if (appConfig.enableMockApi) {
    return getPublicTicketByNumberMock(normalized);
  }

  const response = await fetch(
    `${appConfig.apiBaseUrl}/tickets/public/${encodeURIComponent(normalized)}`,
    {
      method: 'GET',
      headers: getAuthHeaders(),
    },
  );

  if (!response.ok) {
    throw new Error(await parseApiError(response, PUBLIC_TICKETS_NETWORK_MESSAGE));
  }

  return response.json() as Promise<PublicTicketResponse>;
}

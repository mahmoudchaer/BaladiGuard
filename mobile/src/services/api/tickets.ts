import { Platform } from 'react-native';

import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type {
  CitizenTicketResponse,
  SubmitTicketRequest,
  SubmitTicketResponse,
} from '@/types/ticket';
import { appConfig } from '@/services/config';
import { getAuthHeaders, handleUnauthorizedResponse, parseApiError } from '@/services/api/http';
import { getTicketByTrackingCodeMock, submitTicketMock } from '@/services/api/mockTickets';
import { uploadReportPhoto } from '@/services/api/uploads';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export type SubmitReportPhase = 'uploading-photo' | 'submitting-report';

export const TRACK_LOOKUP_NOT_FOUND_MESSAGE =
  "We couldn't find a report with that tracking code. Check the code and try again.";
export const TRACK_LOOKUP_INVALID_MESSAGE =
  'That tracking code is not valid. Use the 6-character code from your submission confirmation.';
export const TRACK_LOOKUP_NETWORK_MESSAGE =
  'Unable to look up that report right now. Please try again.';

type SubmitReportOptions = {
  onProgress?: (phase: SubmitReportPhase) => void;
};

const buildSubmitPayload = (
  values: ReportFormValues,
  imageObjectKey: string,
): SubmitTicketRequest => {
  const preferredChannel = values.email?.trim() ? 'EMAIL' : 'SMS';

  return {
    description: values.description.trim(),
    languageHint: 'auto',
    contact: {
      name: values.contactName?.trim() || undefined,
      phone: values.phone?.trim() || undefined,
      email: values.email?.trim() || undefined,
      preferredChannel,
    },
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
  };
};

const toReportPhoto = (values: ReportFormValues) => ({
  uri: values.photoUri,
  fileName: values.photoFileName?.trim() || `photo-${Date.now()}.jpg`,
  contentType: values.photoContentType?.trim() || 'image/jpeg',
});

export async function submitReport(
  values: ReportFormValues,
  options?: SubmitReportOptions,
): Promise<SubmitTicketResponse> {
  if (appConfig.enableMockApi) {
    const payload = buildSubmitPayload(
      values,
      values.photoFileName ? `reports/mock/${values.photoFileName}` : 'reports/mock/photo.jpg',
    );
    return submitTicketMock(payload);
  }

  options?.onProgress?.('uploading-photo');
  const imageObjectKey = await uploadReportPhoto(toReportPhoto(values));

  options?.onProgress?.('submitting-report');
  const payload = buildSubmitPayload(values, imageObjectKey);

  const response = await fetch(`${appConfig.apiBaseUrl}/tickets`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    handleUnauthorizedResponse(response.status);
    const message = await parseApiError(response, 'Unable to submit your report right now.');
    throw new Error(`Your photo was uploaded, but the report could not be saved. ${message}`);
  }

  return response.json() as Promise<SubmitTicketResponse>;
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

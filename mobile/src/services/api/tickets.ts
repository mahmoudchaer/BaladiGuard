import { Platform } from 'react-native';

import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type { SubmitTicketRequest, SubmitTicketResponse } from '@/types/ticket';
import { appConfig } from '@/services/config';
import { getClientHeaders, parseApiError } from '@/services/api/http';
import { submitTicketMock } from '@/services/api/mockTickets';
import { uploadReportPhoto } from '@/services/api/uploads';

export type SubmitReportPhase = 'uploading-photo' | 'submitting-report';

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
      ...getClientHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to submit your report right now.');
    throw new Error(`Your photo was uploaded, but the report could not be saved. ${message}`);
  }

  return response.json() as Promise<SubmitTicketResponse>;
}

import { Platform } from 'react-native';

import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type { SubmitTicketRequest, SubmitTicketResponse } from '@/types/ticket';
import { appConfig } from '@/services/config';
import { submitTicketMock } from '@/services/api/mockTickets';

const buildSubmitPayload = (values: ReportFormValues): SubmitTicketRequest => {
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
      latitude: values.latitude ?? 33.8938,
      longitude: values.longitude ?? 35.5018,
      addressText: values.addressText.trim(),
      source: values.locationSource,
    },
    imageObjectKey: values.photoFileName
      ? `reports/mock/${values.photoFileName}`
      : 'reports/mock/photo.jpg',
    clientMetadata: {
      platform: Platform.OS,
      appVersion: appConfig.appVersion,
    },
  };
};

export async function submitReport(
  values: ReportFormValues,
): Promise<SubmitTicketResponse> {
  const payload = buildSubmitPayload(values);

  if (appConfig.enableMockApi) {
    return submitTicketMock(payload);
  }

  const response = await fetch(`${appConfig.apiBaseUrl}/tickets`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-Version': `mobile-${appConfig.appVersion}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const message =
      errorBody?.error?.message ?? 'Unable to submit your report right now.';
    throw new Error(message);
  }

  return response.json() as Promise<SubmitTicketResponse>;
}

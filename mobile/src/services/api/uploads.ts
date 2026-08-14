import { fetch } from 'expo/fetch';
import { File } from 'expo-file-system';

import type { ReportPhoto } from '@/types/ticket';
import { appConfig } from '@/services/config';
import { getAuthHeaders, handleUnauthorizedResponse, parseApiError } from '@/services/api/http';

type ReportPhotoUploadResponse = {
  imageObjectKey: string;
};

export async function uploadReportPhoto(photo: ReportPhoto): Promise<string> {
  const formData = new FormData();
  // Current Expo native fetch accepts Blob-compatible File instances. The old
  // React Native `{ uri, name, type }` pseudo-part throws FormDataPart errors.
  const file = new File(photo.uri);
  formData.append('file', file, photo.fileName);

  const response = await fetch(`${appConfig.apiBaseUrl}/uploads/report-photo`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    handleUnauthorizedResponse(response.status);
    const message = await parseApiError(response, 'Unable to upload your photo right now.');
    throw new Error(message);
  }

  const body = (await response.json()) as ReportPhotoUploadResponse;
  const imageObjectKey = body?.imageObjectKey?.trim();

  if (!imageObjectKey) {
    throw new Error('Photo upload succeeded but no image reference was returned.');
  }

  return imageObjectKey;
}

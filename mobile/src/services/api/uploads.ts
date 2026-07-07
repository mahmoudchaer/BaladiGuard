import type { ReportPhoto } from '@/types/ticket';
import { appConfig } from '@/services/config';
import { getClientHeaders, parseApiError } from '@/services/api/http';

type ReportPhotoUploadResponse = {
  imageObjectKey: string;
};

export async function uploadReportPhoto(photo: ReportPhoto): Promise<string> {
  const formData = new FormData();
  formData.append('file', {
    uri: photo.uri,
    name: photo.fileName,
    type: photo.contentType,
  } as unknown as Blob);

  const response = await fetch(`${appConfig.apiBaseUrl}/uploads/report-photo`, {
    method: 'POST',
    headers: getClientHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to upload your photo right now.');
    throw new Error(message);
  }

  const body = (await response.json()) as ReportPhotoUploadResponse;
  return body.imageObjectKey;
}

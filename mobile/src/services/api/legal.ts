import type { LegalCatalog, LegalDocument, LegalDocumentId } from '@/types/legal';
import { appConfig } from '@/services/config';
import { getAuthHeaders, parseApiError } from '@/services/api/http';
import { CitizenAuthApiError } from '@/services/api/citizenAuth';

export type { LegalCatalog, LegalDocument, LegalDocumentId };

async function legalFetch(path: string): Promise<Response> {
  try {
    return await fetch(`${appConfig.apiBaseUrl}${path}`, {
      method: 'GET',
      headers: getAuthHeaders(),
    });
  } catch {
    throw new CitizenAuthApiError('Unable to reach the server. Check your connection and try again.', {
      code: 'NETWORK_ERROR',
      status: 0,
    });
  }
}

export async function getLegalDocument(
  documentId: LegalDocumentId | string,
  lang: string,
): Promise<LegalDocument> {
  const query = new URLSearchParams({ lang });
  const response = await legalFetch(`/legal/${encodeURIComponent(documentId)}?${query}`);
  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to load that legal document.');
    throw new CitizenAuthApiError(message, { code: 'UNKNOWN', status: response.status });
  }
  return response.json() as Promise<LegalDocument>;
}

export async function getLegalCatalog(): Promise<LegalCatalog> {
  const response = await legalFetch('/legal');
  if (!response.ok) {
    const message = await parseApiError(response, 'Unable to load legal documents.');
    throw new CitizenAuthApiError(message, { code: 'UNKNOWN', status: response.status });
  }
  return response.json() as Promise<LegalCatalog>;
}

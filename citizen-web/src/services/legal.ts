import { jsonRequest } from '@/services/api';
import type { LegalCatalog, LegalDocument, LegalDocumentId } from '@/types/legal';

export async function getLegalCatalog(): Promise<LegalCatalog> {
  return jsonRequest('/legal', { method: 'GET' }, 'Unable to load legal documents.');
}

export async function getLegalDocument(
  documentId: LegalDocumentId | string,
  lang: string,
): Promise<LegalDocument> {
  const query = new URLSearchParams({ lang });
  return jsonRequest(
    `/legal/${encodeURIComponent(documentId)}?${query}`,
    { method: 'GET' },
    'Unable to load that legal document.',
  );
}

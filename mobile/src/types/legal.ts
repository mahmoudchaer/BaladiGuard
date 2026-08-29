export type LegalDocumentId = 'terms' | 'privacy' | 'acceptable-use';

export type LegalDocumentSummary = {
  id: LegalDocumentId | string;
  title: string;
  version: string;
  updatedAt: string;
  languages: string[];
};

export type LegalCatalog = {
  version: string;
  documents: LegalDocumentSummary[];
};

export type LegalDocument = {
  id: LegalDocumentId | string;
  title: string;
  version: string;
  updatedAt: string;
  lang: string;
  markdown: string;
};

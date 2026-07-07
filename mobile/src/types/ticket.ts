export type LocationSource = 'GPS' | 'MANUAL' | 'PLACEHOLDER';

export type ReportLocation = {
  latitude: number;
  longitude: number;
  addressText: string;
  source: LocationSource;
};

export type ReportContact = {
  name?: string;
  phone?: string;
  email?: string;
  preferredChannel?: 'SMS' | 'EMAIL';
};

export type SubmitTicketRequest = {
  description: string;
  languageHint: 'auto' | string;
  contact: ReportContact;
  location: ReportLocation;
  imageObjectKey: string;
  clientMetadata: {
    platform: string;
    appVersion: string;
  };
};

export type SubmitTicketResponse = {
  ticketId: string;
  ticketNumber: string;
  trackingCode: string;
  status: 'SUBMITTED';
  message: string;
  createdAt: string;
};

export type TicketStatus = 'SUBMITTED' | 'UNDER_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED';

export type TicketPriority = 'low' | 'medium' | 'high';

export type TicketImageReference = {
  objectKey: string;
  url?: string;
  contentType?: string;
  createdAt?: string;
};

export type TicketDepartment = {
  departmentId?: string;
  name?: string;
};

export type TicketAiFields = {
  cleanedDescription?: string;
  suggestedCategory?: string;
  urgencyReason?: string;
  summary?: string;
};

export type TicketStatusHistoryEntry = {
  status: TicketStatus;
  changedAt: string;
  changedBy?: string;
  note?: string;
};

export type TicketDuplicateReference = {
  duplicateGroupId: string;
  ticketIds?: string[];
  canonicalTicketId?: string;
};

/**
 * Shared ticket read shape returned by staff dashboard and ticket read APIs.
 * This is an API response contract, not the full persistence/database schema.
 */
export type TicketResponse = {
  ticketId: string;
  ticketNumber?: string;
  trackingCode: string;
  description: string;
  contact?: ReportContact | null;
  category: string;
  priority: TicketPriority | null;
  status: TicketStatus;
  location: ReportLocation;
  imageReferences: TicketImageReference[];
  imageObjectKey?: string;
  department: TicketDepartment | null;
  departmentId?: string | null;
  createdAt: string;
  updatedAt: string | null;
  ai?: TicketAiFields;
  statusHistory?: TicketStatusHistoryEntry[];
  duplicateGroup?: TicketDuplicateReference;
};

export type ReportPhoto = {
  uri: string;
  fileName: string;
  contentType: string;
  sizeBytes?: number;
};

export type PlaceholderLocation = {
  id: string;
  label: string;
  addressText: string;
  latitude: number;
  longitude: number;
};

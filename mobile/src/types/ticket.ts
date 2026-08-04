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

export type TicketStatus =
  'SUBMITTED' | 'UNDER_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

/** Public citizen timeline entry from GET /v1/tickets/track/{trackingCode}. */
export type CitizenTicketTimelineEntry = {
  status: TicketStatus;
  changedAt: string;
};

/** Public citizen tracking response — never includes staff-only fields. */
export type CitizenTicketResponse = {
  ticketNumber: string | null;
  trackingCode: string;
  status: TicketStatus;
  category: string | null;
  location: { addressText: string } | null;
  createdAt: string;
  updatedAt: string | null;
  lastUpdatedAt: string;
  timeline: CitizenTicketTimelineEntry[];
};

export type CitizenTicketHistoryItem = {
  trackingCode: string;
  status: TicketStatus;
  category: string | null;
  locationAddress: string;
  submittedAt: string;
};

export type CitizenTicketHistoryResponse = {
  items: CitizenTicketHistoryItem[];
  nextCursor: string | null;
  limit: number;
};

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';

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

export type AiProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type TicketAiFields = {
  originalDescription?: string;
  cleanedDescription?: string;
  aiSuggestedCategory?: string;
  aiCategoryExplanation?: string;
  aiConfidence?: number;
  finalCategory?: string;
  categoryReviewedBy?: string;
  categoryReviewedAt?: string;
  aiProcessingStatus?: AiProcessingStatus;
  aiModelVersion?: string;
  suggestedCategory?: string;
  urgencyScore?: number;
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
  createdBy?: string | null;
  municipalityId?: string | null;
  duplicateGroupId?: string | null;
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

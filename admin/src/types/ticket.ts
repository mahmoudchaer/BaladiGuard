/**
 * Shared ticket shape aligned with:
 * - backend/app/schemas/stored_ticket.py (StoredTicket)
 * - docs/MVP_API_CONTRACT.md persistence mapping
 * - mock_tickets.json fixtures
 *
 * Intended for staff dashboard and future GET /v1/tickets responses.
 */

export type TicketStatus =
  'SUBMITTED' | 'UNDER_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';

export type LocationSource = 'GPS' | 'MANUAL' | 'PLACEHOLDER';

export type TicketContact = {
  name?: string;
  phone?: string;
  email?: string;
};

export type TicketLocation = {
  latitude: number;
  longitude: number;
  addressText: string;
  source: LocationSource;
};

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

export type TicketDuplicateReference = {
  duplicateGroupId: string;
  ticketIds?: string[];
  canonicalTicketId?: string;
};

export type TicketDuplicateSuggestion = {
  ticketId: string;
  ticketNumber?: string;
  distanceMeters: number;
  status: TicketStatus;
  category: string;
  score?: number;
  categoryMatch?: 'same' | 'similar';
};

export type Ticket = {
  ticketId: string;
  ticketNumber: string;
  trackingCode: string;
  description: string;
  contact: TicketContact;
  location: TicketLocation;
  imageObjectKey: string;
  imageUrl?: string;
  imageReferences?: TicketImageReference[];
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  createdBy: string | null;
  municipalityId: string | null;
  departmentId: string | null;
  departmentName?: string;
  department?: TicketDepartment | null;
  duplicateGroupId: string | null;
  duplicateGroup?: TicketDuplicateReference | null;
  duplicateSuggestions?: TicketDuplicateSuggestion[];
  createdAt: string;
  updatedAt: string | null;
  ai?: TicketAiFields;
};

export type TicketListItem = Pick<
  Ticket,
  | 'ticketId'
  | 'ticketNumber'
  | 'category'
  | 'location'
  | 'status'
  | 'priority'
  | 'createdAt'
  | 'duplicateGroupId'
>;

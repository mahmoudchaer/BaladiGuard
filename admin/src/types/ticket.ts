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
  /** Automatic department suggestion; preserved when staff overrides departmentId. */
  suggestedDepartmentId?: string;
  urgencyScore?: number;
  urgencyReason?: string;
  summary?: string;
};

export type TicketStatusHistoryEntry = {
  status: TicketStatus;
  changedAt: string;
  changedBy?: string | null;
  note?: string | null;
};

export type StaffComment = {
  commentId: string;
  ticketId: string;
  authorStaffId: string;
  authorDisplayName: string;
  text: string;
  mentionedStaffIds: string[];
  createdAt: string;
};
export type ActivityEvent = {
  eventId: string;
  eventType: string;
  occurredAt: string;
  actorDisplayName?: string | null;
  details: Record<string, string>;
  sourceReference: string;
};

export type ActivityPage = { events: ActivityEvent[]; nextCursor: string | null };

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

export type PublicTicketStatus = 'DRAFT' | 'PUBLISHED' | 'UNPUBLISHED';

export type TicketPublicFields = {
  status: PublicTicketStatus;
  description?: string | null;
  locationLabel?: string | null;
  imageObjectKey?: string | null;
  publishedAt?: string | null;
};

export type TicketSla = {
  state: 'on_track' | 'due_soon' | 'overdue' | 'completed' | 'unavailable';
  acknowledgementDueAt?: string | null;
  resolutionDueAt?: string | null;
  targetAt?: string | null;
  remainingSeconds?: number | null;
  overdueSeconds?: number | null;
  policyKey?: TicketPriority | null;
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
  statusHistory?: TicketStatusHistoryEntry[];
  createdAt: string;
  updatedAt: string | null;
  updatedBy?: string | null;
  ai?: TicketAiFields;
  sla?: TicketSla | null;
  public?: TicketPublicFields;
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

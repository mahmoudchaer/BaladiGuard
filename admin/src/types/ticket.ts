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

export type TicketAuditActionType =
  | 'STATUS_CHANGE'
  | 'CATEGORY_REVIEW'
  | 'DEPARTMENT_ASSIGN'
  | 'DUPLICATE_MERGE'
  | 'PUBLIC_CONTENT_UPDATE';

export type TicketStaffRole = 'municipal_staff' | 'administrator';

/**
 * Staff-only audit entry returned by the ticket read endpoint.
 * Mirrors backend/app/schemas/ticket_response.py TicketAuditHistoryEntry.
 */
export type TicketAuditHistoryEntry = {
  actionType: TicketAuditActionType;
  summary: string;
  changedAt: string;
  actorId?: string;
  actorRole?: TicketStaffRole;
  previousValue?: string;
  newValue?: string;
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

/** Coarse location shared by the bounded duplicate-workspace projections. */
export type DuplicateLocation = {
  latitude: number;
  longitude: number;
  addressText: string;
};

/**
 * One mergeable candidate from `GET /v1/tickets/{id}/duplicate-candidates`.
 *
 * The endpoint only returns ungrouped, open tickets that share the source's
 * effective category, so every candidate satisfies the merge preconditions.
 */
export type DuplicateCandidate = {
  ticketId: string;
  ticketNumber: string;
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  summary: string;
  createdAt: string;
  location: DuplicateLocation;
  distanceMeters?: number;
  /** Presigned URL only; raw storage keys are never exposed. */
  imageUrl?: string;
  /** Surfaced by the automated duplicate detector rather than staff browsing. */
  suggested: boolean;
  score?: number;
  categoryMatch?: 'same' | 'similar';
  mergeable: boolean;
};

export type DuplicateCandidatePage = {
  items: DuplicateCandidate[];
  nextCursor: string | null;
  limit: number;
};

/**
 * Bounded projection used for the side-by-side duplicate comparison.
 *
 * Deliberately excludes citizen contact details, tracking codes, raw storage
 * keys, audit/status history, AI fields, and public-content drafts: staff
 * comparing candidates only need the evidence to judge whether two reports
 * describe the same problem.
 */
export type DuplicateComparison = {
  ticketId: string;
  ticketNumber: string;
  description: string;
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  createdAt: string;
  location: DuplicateLocation;
  imageUrl?: string;
  distanceMeters?: number;
};

export type PublicTicketStatus = 'DRAFT' | 'PUBLISHED' | 'UNPUBLISHED';

export type TicketPublicFields = {
  status: PublicTicketStatus;
  description?: string | null;
  locationLabel?: string | null;
  imageObjectKey?: string | null;
  publishedAt?: string | null;
};

export type ImageRedactionStatus =
  'pending' | 'processing' | 'completed' | 'failed' | 'review_required';

export type TicketImageRedaction = {
  status: ImageRedactionStatus;
  generation: number;
  detector?: string | null;
  detectorVersion?: string | null;
  faceCount: number;
  plateCount: number;
  completedAt?: string | null;
  reasonCode?: string | null;
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
  auditHistory?: TicketAuditHistoryEntry[];
  createdAt: string;
  updatedAt: string | null;
  updatedBy?: string | null;
  ai?: TicketAiFields;
  sla?: TicketSla | null;
  public?: TicketPublicFields;
  imageRedaction?: TicketImageRedaction;
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

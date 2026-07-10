/**
 * Shared ticket shape aligned with:
 * - backend/app/schemas/stored_ticket.py (StoredTicket)
 * - docs/MVP_API_CONTRACT.md persistence mapping
 * - mock_tickets.json fixtures
 *
 * Intended for staff dashboard and future GET /v1/tickets responses.
 */

export type TicketStatus =
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED';

export type TicketPriority = 'low' | 'medium' | 'high';

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
  createdAt: string;
  updatedAt: string | null;
};

export type TicketListItem = Pick<
  Ticket,
  'ticketId' | 'ticketNumber' | 'category' | 'location' | 'status' | 'priority' | 'createdAt'
>;

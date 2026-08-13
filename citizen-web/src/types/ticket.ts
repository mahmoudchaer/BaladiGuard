/** Citizen-safe ticket types aligned with mobile/src/types/ticket.ts and MVP_API_CONTRACT. */

export type TicketStatus =
  'SUBMITTED' | 'UNDER_REVIEW' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

export type PublicTicketAttribution = {
  displayName: string;
  isNamed: boolean;
};

/**
 * Public browse/detail projection.
 * Never includes ticketId, trackingCode, contacts, private locations, staff history,
 * or private image keys.
 */
export type PublicTicketResponse = {
  ticketNumber: string;
  status: TicketStatus;
  category: string | null;
  description: string;
  location: { addressText: string };
  mapLocation: {
    addressText: string;
    latitude: number;
    longitude: number;
  };
  department?: { name: string } | null;
  attribution: PublicTicketAttribution;
  photoUrl?: string | null;
  createdAt: string;
  updatedAt: string | null;
};

export type PublicTicketListResponse = {
  items: PublicTicketResponse[];
  nextCursor: string | null;
  limit: number;
};

export type CitizenTicketTimelineEntry = {
  status: TicketStatus;
  changedAt: string;
};

/** Possession-based tracking response — includes trackingCode, never staff-only fields. */
export type CitizenTicketResponse = {
  ticketNumber: string | null;
  trackingCode: string;
  status: TicketStatus;
  category: string | null;
  location: { addressText: string } | null;
  department?: { name: string } | null;
  createdAt: string;
  updatedAt: string | null;
  lastUpdatedAt: string;
  timeline: CitizenTicketTimelineEntry[];
};

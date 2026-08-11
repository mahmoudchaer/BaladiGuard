import type { Ticket, TicketLocation, TicketPriority, TicketStatus } from '@/types/ticket';
import { effectiveTicketCategory } from '@/utils/ticketCategory';
import { isPlottableLocation } from '@/utils/ticketLocation';

/**
 * Bounded projection used for the side-by-side duplicate comparison.
 *
 * Deliberately excludes citizen contact details, tracking codes, raw storage
 * keys, audit history, and public-content fields: staff comparing candidates
 * only need the evidence needed to judge whether two reports are the same.
 */
export type DuplicateComparison = {
  ticketId: string;
  ticketNumber: string;
  description: string;
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  createdAt: string;
  location: TicketLocation;
  imageUrl?: string;
  /** Kept only to resolve a display image; never rendered as ordinary content. */
  imageObjectKey: string;
};

export function toDuplicateComparison(ticket: Ticket): DuplicateComparison {
  return {
    ticketId: ticket.ticketId,
    ticketNumber: ticket.ticketNumber,
    description: ticket.description,
    status: ticket.status,
    category: effectiveTicketCategory(ticket) ?? ticket.category,
    priority: ticket.priority,
    createdAt: ticket.createdAt,
    location: { ...ticket.location },
    imageUrl: ticket.imageUrl,
    imageObjectKey: ticket.imageObjectKey,
  };
}

const EARTH_RADIUS_METERS = 6371000;

function toRadians(degrees: number): number {
  return (degrees * Math.PI) / 180;
}

/** Great-circle distance, used when a candidate carries no server distance. */
export function distanceMetersBetween(
  from: Partial<TicketLocation> | null | undefined,
  to: Partial<TicketLocation> | null | undefined,
): number | null {
  if (!isPlottableLocation(from) || !isPlottableLocation(to)) {
    return null;
  }

  const deltaLat = toRadians(to.latitude - from.latitude);
  const deltaLng = toRadians(to.longitude - from.longitude);
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(toRadians(from.latitude)) *
      Math.cos(toRadians(to.latitude)) *
      Math.sin(deltaLng / 2) ** 2;

  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function formatDistanceMeters(distanceMeters: number): string {
  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(1)} km away`;
  }

  return `${Math.round(distanceMeters)} m away`;
}

/** Short, single-line excerpt of a citizen description for candidate rows. */
export function describeExcerpt(description: string | undefined, maxLength = 120): string {
  const normalized = (description ?? '').replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return 'No description provided.';
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`;
}

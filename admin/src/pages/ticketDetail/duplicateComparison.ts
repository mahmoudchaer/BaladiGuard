import type { DuplicateComparison, Ticket } from '@/types/ticket';
import { effectiveTicketCategory } from '@/utils/ticketCategory';

export type { DuplicateComparison };
export { distanceMetersBetween } from '@/utils/ticketLocation';

/**
 * Projects the already-loaded ticket into the comparison shape so the current
 * ticket column matches the bounded projection the API returns for candidates.
 */
export function toDuplicateComparison(ticket: Ticket): DuplicateComparison {
  return {
    ticketId: ticket.ticketId,
    ticketNumber: ticket.ticketNumber,
    description: ticket.description,
    status: ticket.status,
    category: effectiveTicketCategory(ticket) ?? ticket.category,
    priority: ticket.priority,
    createdAt: ticket.createdAt,
    location: {
      latitude: ticket.location.latitude,
      longitude: ticket.location.longitude,
      addressText: ticket.location.addressText,
    },
    imageUrl: ticket.imageUrl,
  };
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

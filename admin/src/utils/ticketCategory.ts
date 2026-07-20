import type { Ticket } from '@/types/ticket';

export const PENDING_CLASSIFICATION = 'PENDING_CLASSIFICATION';

/**
 * Category a staff member should treat as the ticket's real category.
 * Mirrors backend `effective_ticket_category`: staff-reviewed final category,
 * else the AI suggestion, else the stored category when already classified.
 * Returns null while the ticket is still pending classification so callers
 * handle unclassified tickets explicitly.
 */
export function effectiveTicketCategory(ticket: Ticket): string | null {
  if (ticket.ai?.finalCategory) {
    return ticket.ai.finalCategory;
  }
  if (ticket.ai?.aiSuggestedCategory) {
    return ticket.ai.aiSuggestedCategory;
  }
  if (ticket.category && ticket.category !== PENDING_CLASSIFICATION) {
    return ticket.category;
  }
  return null;
}

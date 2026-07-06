import type { Ticket, TicketStatus } from '@/types/ticket';

export type TicketStats = {
  total: number;
  open: number;
  highUrgency: number;
  resolved: number;
  inProgress: number;
};

const OPEN_STATUSES: TicketStatus[] = ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS'];

export function computeTicketStats(tickets: Ticket[]): TicketStats {
  return {
    total: tickets.length,
    open: tickets.filter((t) => OPEN_STATUSES.includes(t.status)).length,
    highUrgency: tickets.filter((t) => t.priority === 'high').length,
    resolved: tickets.filter((t) => t.status === 'RESOLVED').length,
    inProgress: tickets.filter((t) => t.status === 'IN_PROGRESS').length,
  };
}

export type StatusFilter = 'ALL' | TicketStatus;

export function filterTickets(
  tickets: Ticket[],
  searchQuery: string,
  statusFilter: StatusFilter,
): Ticket[] {
  const query = searchQuery.trim().toLowerCase();

  return tickets.filter((ticket) => {
    if (statusFilter !== 'ALL' && ticket.status !== statusFilter) {
      return false;
    }

    if (!query) {
      return true;
    }

    const haystack = [
      ticket.ticketNumber,
      ticket.trackingCode,
      ticket.description,
      ticket.location.addressText,
      ticket.category,
    ]
      .join(' ')
      .toLowerCase();

    return haystack.includes(query);
  });
}

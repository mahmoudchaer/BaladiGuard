import { t } from '@/i18n';
import type { Ticket, TicketPriority, TicketStatus } from '@/types/ticket';
import { SUPPORTED_CATEGORY_OPTIONS } from '@/utils/labels';

export type TicketStats = {
  total: number;
  open: number;
  highUrgency: number;
  completed: number;
  inProgress: number;
};

/** Compact operational attention counts for the work queue. */
export type QueueAttentionStats = {
  critical: number;
  unassigned: number;
  aging: number;
};

const OPEN_STATUSES: TicketStatus[] = ['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS'];
const AGING_MS = 3 * 24 * 60 * 60 * 1000;

export function computeTicketStats(tickets: Ticket[]): TicketStats {
  return {
    total: tickets.length,
    open: tickets.filter((t) => OPEN_STATUSES.includes(t.status)).length,
    highUrgency: tickets.filter((t) => t.priority === 'high' || t.priority === 'critical').length,
    completed: tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED').length,
    inProgress: tickets.filter((t) => t.status === 'IN_PROGRESS').length,
  };
}

function isOpenTicket(ticket: Ticket): boolean {
  return OPEN_STATUSES.includes(ticket.status);
}

export function computeQueueAttentionStats(
  tickets: Ticket[],
  now = Date.now(),
): QueueAttentionStats {
  return {
    critical: tickets.filter((ticket) => isOpenTicket(ticket) && ticket.priority === 'critical')
      .length,
    unassigned: tickets.filter((ticket) => isOpenTicket(ticket) && !ticket.departmentId).length,
    aging: tickets.filter((ticket) => {
      if (!isOpenTicket(ticket)) {
        return false;
      }
      const createdAt = Date.parse(ticket.createdAt);
      return Number.isFinite(createdAt) && now - createdAt >= AGING_MS;
    }).length,
  };
}

export type StatusFilter = 'ALL' | TicketStatus;
export type CategoryFilter = 'ALL' | string;
export type UrgencyFilter = 'ALL' | TicketPriority;
export type DepartmentFilter = 'ALL' | string;

export type CategoryFilterOption = {
  value: CategoryFilter;
  label: string;
};

export function getCategoryFilterOptions(
  tickets: Ticket[],
  translate: (key: string, vars?: Record<string, string | number>) => string = t,
): CategoryFilterOption[] {
  const categories = Array.from(
    new Set([...SUPPORTED_CATEGORY_OPTIONS, ...tickets.map((ticket) => ticket.category)]),
  ).sort((a, b) => a.localeCompare(b));

  return [
    { value: 'ALL', label: translate('filters.allCategories') },
    ...categories.map((category) => ({
      value: category,
      label: category,
    })),
  ];
}

export function filterTickets(
  tickets: Ticket[],
  searchQuery: string,
  statusFilter: StatusFilter,
  categoryFilter: CategoryFilter,
  urgencyFilter: UrgencyFilter = 'ALL',
  departmentFilter: DepartmentFilter = 'ALL',
): Ticket[] {
  const query = searchQuery.trim().toLowerCase();

  return tickets.filter((ticket) => {
    if (statusFilter !== 'ALL' && ticket.status !== statusFilter) {
      return false;
    }

    if (categoryFilter !== 'ALL' && ticket.category !== categoryFilter) {
      return false;
    }

    if (urgencyFilter !== 'ALL' && ticket.priority !== urgencyFilter) {
      return false;
    }

    if (departmentFilter !== 'ALL' && ticket.departmentId !== departmentFilter) {
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

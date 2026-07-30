import type { Ticket, TicketPriority, TicketStatus } from '@/types/ticket';
import { SUPPORTED_CATEGORY_OPTIONS } from '@/utils/labels';

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
    highUrgency: tickets.filter((t) => t.priority === 'high' || t.priority === 'critical').length,
    resolved: tickets.filter((t) => t.status === 'RESOLVED').length,
    inProgress: tickets.filter((t) => t.status === 'IN_PROGRESS').length,
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

export function getCategoryFilterOptions(tickets: Ticket[]): CategoryFilterOption[] {
  const categories = Array.from(
    new Set([...SUPPORTED_CATEGORY_OPTIONS, ...tickets.map((ticket) => ticket.category)]),
  ).sort((a, b) => a.localeCompare(b));

  return [
    { value: 'ALL', label: 'All categories' },
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

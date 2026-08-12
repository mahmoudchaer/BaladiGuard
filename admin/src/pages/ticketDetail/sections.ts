/**
 * Ticket detail workspace sections.
 *
 * The active section lives in the `section` search param so refresh, deep
 * links, and browser back/forward stay predictable. Section changes are local
 * only: the authoritative ticket detail is loaded once per route entry.
 */

export const TICKET_DETAIL_SECTIONS = ['overview', 'review', 'duplicates', 'activity'] as const;

export type TicketDetailSection = (typeof TICKET_DETAIL_SECTIONS)[number];

export const TICKET_DETAIL_SECTION_PARAM = 'section';

export const DEFAULT_TICKET_DETAIL_SECTION: TicketDetailSection = 'overview';

export const TICKET_DETAIL_SECTION_LABELS: Record<TicketDetailSection, string> = {
  overview: 'Overview',
  review: 'Review & Actions',
  duplicates: 'Duplicates',
  activity: 'Activity',
};

/** Unknown or missing values fall back to Overview instead of erroring. */
export function parseTicketDetailSection(value: string | null | undefined): TicketDetailSection {
  const normalized = value?.trim().toLowerCase();
  return (
    TICKET_DETAIL_SECTIONS.find((section) => section === normalized) ??
    DEFAULT_TICKET_DETAIL_SECTION
  );
}

export function ticketDetailTabId(section: TicketDetailSection): string {
  return `ticket-section-tab-${section}`;
}

export function ticketDetailPanelId(section: TicketDetailSection): string {
  return `ticket-section-panel-${section}`;
}

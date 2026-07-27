import { StatusBadge } from '@/components/StatusBadge';
import type { TicketStatusHistoryEntry } from '@/types/ticket';
import { formatCreatedDate } from '@/utils/labels';
import { normalizeTimelineEvents } from '@/utils/timeline';
import './TicketTimeline.css';

export type TicketTimelineVariant = 'staff' | 'citizen';

export type TicketTimelineProps = {
  history?: TicketStatusHistoryEntry[] | null;
  /**
   * Staff view shows actor and notes.
   * Citizen view is status + timestamp only (hides staff-only actor/notes).
   */
  variant?: TicketTimelineVariant;
  emptyMessage?: string;
};

export function TicketTimeline({
  history,
  variant = 'staff',
  emptyMessage = 'No status history is available for this ticket yet.',
}: TicketTimelineProps) {
  const events = normalizeTimelineEvents(history);
  const showStaffDetails = variant === 'staff';

  if (events.length === 0) {
    return (
      <p className="ticket-timeline__empty" role="status">
        {emptyMessage}
      </p>
    );
  }

  return (
    <ol className="ticket-timeline" aria-label="Ticket status timeline">
      {events.map((event, index) => {
        const isLatest = index === events.length - 1;
        return (
          <li
            key={`${event.changedAt}-${event.status}-${index}`}
            className={`ticket-timeline__item${isLatest ? ' ticket-timeline__item--latest' : ''}`}
          >
            <div className="ticket-timeline__marker" aria-hidden="true" />
            <div className="ticket-timeline__content">
              <div className="ticket-timeline__header">
                <StatusBadge status={event.status} />
                <time className="ticket-timeline__time" dateTime={event.changedAt}>
                  {formatCreatedDate(event.changedAt)}
                </time>
              </div>
              {showStaffDetails && event.changedBy ? (
                <p className="ticket-timeline__actor">Updated by {event.changedBy}</p>
              ) : null}
              {showStaffDetails && event.note ? (
                <p className="ticket-timeline__note">{event.note}</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

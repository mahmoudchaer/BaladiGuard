import { useNavigate } from 'react-router-dom';
import { IconTicket } from '@/components/icons';
import type { Ticket } from '@/types/ticket';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityBadge } from '@/components/PriorityBadge';
import { CategoryBadge } from '@/components/CategoryBadge';
import { formatCreatedDate } from '@/utils/labels';
import './TicketTable.css';

type TicketTableProps = {
  tickets: Ticket[];
};

export function TicketTable({ tickets }: TicketTableProps) {
  const navigate = useNavigate();

  const openTicket = (ticketId: string) => {
    navigate(`/tickets/${ticketId}`);
  };

  return (
    <div className="ticket-table-panel">
      <div className="ticket-table-panel__header">
        <h2 className="ticket-table-panel__title">All Tickets</h2>
      </div>
      <div className="ticket-table-wrapper">
        <table className="ticket-table">
          <caption className="sr-only">Submitted infrastructure tickets</caption>
          <thead>
            <tr>
              <th scope="col">Ticket ID</th>
              <th scope="col">Category</th>
              <th scope="col">Location</th>
              <th scope="col">Status</th>
              <th scope="col">Urgency</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((ticket) => (
              <tr
                key={ticket.ticketId}
                className="ticket-table__row ticket-table__row--clickable"
                onClick={() => openTicket(ticket.ticketId)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openTicket(ticket.ticketId);
                  }
                }}
                tabIndex={0}
                role="link"
                aria-label={`View ticket ${ticket.ticketNumber}`}
              >
                <td data-label="Ticket ID">
                  <div className="ticket-table__id-cell">
                    <span className="ticket-table__id-icon" aria-hidden="true">
                      <IconTicket />
                    </span>
                    <div>
                      <span className="ticket-table__ticket-number">{ticket.ticketNumber}</span>
                      <span className="ticket-table__tracking-code">{ticket.trackingCode}</span>
                    </div>
                  </div>
                </td>
                <td data-label="Category">
                  <CategoryBadge category={ticket.category} />
                </td>
                <td data-label="Location">
                  <span className="ticket-table__location">{ticket.location.addressText}</span>
                </td>
                <td data-label="Status">
                  <StatusBadge status={ticket.status} />
                </td>
                <td data-label="Urgency">
                  <PriorityBadge priority={ticket.priority} />
                </td>
                <td data-label="Created">
                  <time className="ticket-table__date" dateTime={ticket.createdAt}>
                    {formatCreatedDate(ticket.createdAt)}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

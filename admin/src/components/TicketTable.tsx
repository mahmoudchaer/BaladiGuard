import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { Ticket } from '@/types/ticket';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityBadge } from '@/components/PriorityBadge';
import { CategoryBadge } from '@/components/CategoryBadge';
import { formatDepartment } from '@/utils/departments';
import { formatTicketAge } from '@/utils/labels';
import { useI18n } from '@/i18n/LocaleProvider';
import './TicketTable.css';

function QueueThumb({ ticket }: { ticket: Ticket }) {
  const [failed, setFailed] = useState(false);
  const url = ticket.imageUrl;

  if (!url || failed) {
    return (
      <span className="ticket-queue__thumb ticket-queue__thumb--empty" aria-hidden="true">
        No photo
      </span>
    );
  }

  return (
    <img
      className="ticket-queue__thumb"
      src={url}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

type TicketTableProps = {
  tickets: Ticket[];
  title?: string;
  selectedTicketId?: string | null;
  onSelectTicket?: (ticketId: string) => void;
  checkedTicketIds?: string[];
  onToggleChecked?: (ticketId: string) => void;
  onToggleAllChecked?: () => void;
};

function departmentLabel(ticket: Ticket): string {
  if (ticket.departmentName) {
    return ticket.departmentName;
  }
  if (ticket.departmentId) {
    return formatDepartment(ticket.departmentId);
  }
  return 'Unassigned';
}

function departmentInitials(label: string): string {
  return label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function TicketTable({
  tickets,
  title = 'Citizen reports',
  selectedTicketId = null,
  onSelectTicket,
  checkedTicketIds = [],
  onToggleChecked,
  onToggleAllChecked,
}: TicketTableProps) {
  const navigate = useNavigate();
  const { t } = useI18n();

  const openTicket = (ticketId: string) => {
    navigate(`/tickets/${ticketId}`);
  };

  return (
    <div className="ticket-table-panel">
      <div className="ticket-table-panel__header">
        <div>
          <h2 className="ticket-table-panel__title">{title}</h2>
          <p className="ticket-table-panel__subtitle">
            Select a report to preview · open for full municipal actions
          </p>
          {onToggleAllChecked ? (
            <label className="ticket-queue__select-all">
              <input
                type="checkbox"
                checked={
                  tickets.length > 0 &&
                  tickets.every((ticket) => checkedTicketIds.includes(ticket.ticketId))
                }
                onChange={onToggleAllChecked}
              />
              {t('tickets.bulk.selectAll')}
            </label>
          ) : null}
        </div>
        <Link to="/map" className="ticket-table-panel__map-link">
          Open map view
        </Link>
      </div>

      <div className="ticket-queue" role="list" aria-label="Submitted infrastructure tickets">
        {tickets.map((ticket) => {
          const owner = departmentLabel(ticket);
          const isUnassigned = !ticket.departmentId;
          const isCritical = ticket.priority === 'critical';
          const selected = selectedTicketId === ticket.ticketId;

          return (
            <div
              key={ticket.ticketId}
              className={[
                'ticket-queue__item',
                selected ? 'ticket-queue__item--selected' : '',
                isCritical ? 'ticket-queue__item--critical' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              role="listitem"
            >
              {onToggleChecked ? (
                <label className="ticket-queue__bulk">
                  <input
                    type="checkbox"
                    checked={checkedTicketIds.includes(ticket.ticketId)}
                    onChange={() => onToggleChecked(ticket.ticketId)}
                    aria-label={t('tickets.bulk.selectTicket', { number: ticket.ticketNumber })}
                  />
                </label>
              ) : null}
              <button
                type="button"
                className="ticket-queue__select"
                onClick={() => {
                  onSelectTicket?.(ticket.ticketId);
                }}
                aria-pressed={selected}
                aria-label={`Select ticket ${ticket.ticketNumber}`}
              >
                <div className="ticket-queue__row">
                  <QueueThumb ticket={ticket} />
                  <div className="ticket-queue__content">
                    <div className="ticket-queue__top">
                      <span className="ticket-queue__number">{ticket.ticketNumber}</span>
                      <time className="ticket-queue__age" dateTime={ticket.createdAt}>
                        {formatTicketAge(ticket.createdAt)}
                      </time>
                    </div>

                    <p className="ticket-queue__description" title={ticket.description}>
                      {ticket.description}
                    </p>

                    <div className="ticket-queue__meta">
                      <StatusBadge status={ticket.status} />
                      <PriorityBadge priority={ticket.priority} />
                      <CategoryBadge category={ticket.category} />
                      {ticket.sla && ticket.sla.state !== 'unavailable' && (
                        <span aria-label={`SLA ${ticket.sla.state.replace('_', ' ')}`}>
                          SLA: {ticket.sla.state.replace('_', ' ')}
                        </span>
                      )}
                    </div>

                    <div className="ticket-queue__footer">
                      <span className="ticket-queue__location">{ticket.location.addressText}</span>
                      <span
                        className={`ticket-queue__owner${
                          isUnassigned ? ' ticket-queue__owner--unassigned' : ''
                        }`}
                        title={owner}
                      >
                        <span className="ticket-queue__avatar" aria-hidden="true">
                          {departmentInitials(owner) || '—'}
                        </span>
                        <span className="ticket-queue__owner-label">{owner}</span>
                      </span>
                    </div>

                    {ticket.trackingCode ? (
                      <span className="ticket-queue__tracking">{ticket.trackingCode}</span>
                    ) : null}
                    {ticket.duplicateGroupId ? (
                      <span className="ticket-queue__grouped">Grouped</span>
                    ) : null}
                  </div>
                </div>
              </button>

              <button
                type="button"
                className="ticket-queue__open"
                onClick={() => openTicket(ticket.ticketId)}
                aria-label={`View ticket ${ticket.ticketNumber}`}
              >
                Open
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

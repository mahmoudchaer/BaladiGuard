import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { Ticket, TicketStatus } from '@/types/ticket';
import { fetchTicketById, updateTicketStatus } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { EmptyState } from '@/components/EmptyState';
import { TicketPhoto } from '@/components/TicketPhoto';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityBadge } from '@/components/PriorityBadge';
import { CategoryBadge } from '@/components/CategoryBadge';
import { formatCreatedDate, formatStatus } from '@/utils/labels';
import { formatDepartment } from '@/utils/departments';
import { statusToModifier } from '@/utils/statusTheme';
import { getSelectableTicketStatuses } from '@/utils/statusTransitions';
import { IconClock, IconDocument, IconHash, IconLocation, IconWorkflow } from '@/components/icons';
import './TicketDetailPage.css';

type LoadState = 'loading' | 'success' | 'not-found' | 'error';

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  useEffect(() => {
    if (!ticketId) {
      setLoadState('not-found');
      return;
    }

    const requestedTicketId = ticketId;
    let cancelled = false;

    async function loadTicket() {
      setLoadState('loading');
      setErrorMessage(null);

      try {
        const data = await fetchTicketById(requestedTicketId);
        if (cancelled) {
          return;
        }

        if (!data) {
          setTicket(null);
          setLoadState('not-found');
          return;
        }

        setTicket(data);
        setLoadState('success');
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load ticket.');
          setLoadState('error');
        }
      }
    }

    void loadTicket();

    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  const handleStatusChange = async (status: TicketStatus) => {
    if (!ticket || status === ticket.status) {
      return;
    }

    setIsUpdatingStatus(true);
    setStatusUpdateError(null);

    try {
      const updatedTicket = await updateTicketStatus(ticket.ticketId, status);

      if (!updatedTicket) {
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      setTicket(updatedTicket);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to update ticket status.';
      setStatusUpdateError(message);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  return (
    <DashboardLayout
      title="Ticket Details"
      subtitle={
        ticket ? `${ticket.ticketNumber} · ${ticket.trackingCode}` : 'View a single citizen report'
      }
    >
      <div className="ticket-detail-page">
        <Link to="/" className="ticket-detail-page__back">
          ← Back to ticket list
        </Link>

        {loadState === 'loading' && <LoadingState message="Loading ticket details…" />}

        {loadState === 'error' && (
          <div className="ticket-detail-page__error" role="alert">
            <h3>Unable to load ticket</h3>
            <p>{errorMessage}</p>
          </div>
        )}

        {loadState === 'not-found' && (
          <EmptyState
            title="Ticket not found"
            message="This ticket may have been removed or the link is incorrect. Return to the list to browse available reports."
          />
        )}

        {loadState === 'success' && ticket && (
          <div className="ticket-detail">
            <header
              className={`ticket-detail__hero ticket-detail__hero--${statusToModifier(ticket.status)}`}
            >
              <div className="ticket-detail__hero-text">
                <CategoryBadge category={ticket.category} />
                <h1 className="ticket-detail__hero-title">{ticket.ticketNumber}</h1>
                <p className="ticket-detail__hero-sub">
                  Tracking code <strong>{ticket.trackingCode}</strong>
                </p>
              </div>
              <div className="ticket-detail__hero-badges">
                <StatusBadge status={ticket.status} />
                <PriorityBadge priority={ticket.priority} />
              </div>
            </header>

            <div className="ticket-detail__body">
              <section className="ticket-detail__main" aria-labelledby="ticket-description-heading">
                <TicketPhoto
                  imageObjectKey={ticket.imageObjectKey}
                  imageUrl={ticket.imageUrl}
                  category={ticket.category}
                  alt={`Report photo for ${ticket.ticketNumber}`}
                />

                <div className="ticket-detail__description-card ticket-detail__card--description">
                  <h2 id="ticket-description-heading" className="ticket-detail__section-title">
                    <span className="ticket-detail__section-icon" aria-hidden="true">
                      <IconDocument />
                    </span>
                    Description
                  </h2>
                  <p className="ticket-detail__description">{ticket.description}</p>
                </div>

                <div className="ticket-detail__location-card ticket-detail__card--location">
                  <h2 className="ticket-detail__section-title">
                    <span className="ticket-detail__section-icon" aria-hidden="true">
                      <IconLocation />
                    </span>
                    Location
                  </h2>
                  <p className="ticket-detail__location-text">{ticket.location.addressText}</p>
                  <p className="ticket-detail__coordinates">
                    {ticket.location.latitude.toFixed(5)}, {ticket.location.longitude.toFixed(5)}
                    <span className="ticket-detail__location-source">
                      {' '}
                      · {ticket.location.source}
                    </span>
                  </p>
                </div>
              </section>

              <aside className="ticket-detail__sidebar" aria-label="Ticket metadata">
                <div className="ticket-detail__meta-card ticket-detail__card--id">
                  <h2 className="ticket-detail__section-title">
                    <span className="ticket-detail__section-icon" aria-hidden="true">
                      <IconHash />
                    </span>
                    Ticket ID
                  </h2>
                  <dl className="ticket-detail__meta-list">
                    <div className="ticket-detail__meta-row">
                      <dt>Ticket number</dt>
                      <dd>{ticket.ticketNumber}</dd>
                    </div>
                    <div className="ticket-detail__meta-row">
                      <dt>Tracking code</dt>
                      <dd className="ticket-detail__mono">{ticket.trackingCode}</dd>
                    </div>
                    <div className="ticket-detail__meta-row">
                      <dt>Internal ID</dt>
                      <dd className="ticket-detail__mono ticket-detail__mono--truncate">
                        {ticket.ticketId}
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className="ticket-detail__meta-card ticket-detail__card--workflow">
                  <h2 className="ticket-detail__section-title">
                    <span className="ticket-detail__section-icon" aria-hidden="true">
                      <IconWorkflow />
                    </span>
                    Workflow
                  </h2>
                  <dl className="ticket-detail__meta-list">
                    <div className="ticket-detail__meta-row ticket-detail__meta-row--badge">
                      <dt>Status</dt>
                      <dd>
                        <StatusBadge status={ticket.status} />
                      </dd>
                    </div>
                    <div className="ticket-detail__meta-row">
                      <dt>Update status</dt>
                      <dd>
                        <select
                          className="ticket-detail__status-select"
                          value={ticket.status}
                          onChange={(event) =>
                            void handleStatusChange(event.target.value as TicketStatus)
                          }
                          disabled={isUpdatingStatus}
                          aria-label="Update ticket status"
                        >
                          {getSelectableTicketStatuses(ticket.status).map((status) => (
                            <option key={status} value={status}>
                              {formatStatus(status)}
                            </option>
                          ))}
                        </select>
                      </dd>
                    </div>
                    {isUpdatingStatus && (
                      <div className="ticket-detail__meta-row">
                        <dt>Status update</dt>
                        <dd className="ticket-detail__status-message">Saving...</dd>
                      </div>
                    )}
                    {statusUpdateError && (
                      <div className="ticket-detail__status-error" role="alert">
                        {statusUpdateError}
                      </div>
                    )}
                    <div className="ticket-detail__meta-row ticket-detail__meta-row--badge">
                      <dt>Category</dt>
                      <dd>
                        <CategoryBadge category={ticket.category} />
                      </dd>
                    </div>
                    <div className="ticket-detail__meta-row ticket-detail__meta-row--badge">
                      <dt>Urgency</dt>
                      <dd>
                        <PriorityBadge priority={ticket.priority} />
                      </dd>
                    </div>
                    <div className="ticket-detail__meta-row">
                      <dt>Department</dt>
                      <dd>
                        <span className="ticket-detail__department">
                          {ticket.departmentName ?? formatDepartment(ticket.departmentId)}
                        </span>
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className="ticket-detail__meta-card ticket-detail__card--timeline">
                  <h2 className="ticket-detail__section-title">
                    <span className="ticket-detail__section-icon" aria-hidden="true">
                      <IconClock />
                    </span>
                    Timeline
                  </h2>
                  <dl className="ticket-detail__meta-list">
                    <div className="ticket-detail__meta-row">
                      <dt>Created</dt>
                      <dd>
                        <time dateTime={ticket.createdAt}>
                          {formatCreatedDate(ticket.createdAt)}
                        </time>
                      </dd>
                    </div>
                    {ticket.updatedAt && (
                      <div className="ticket-detail__meta-row">
                        <dt>Updated</dt>
                        <dd>
                          <time dateTime={ticket.updatedAt}>
                            {formatCreatedDate(ticket.updatedAt)}
                          </time>
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              </aside>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

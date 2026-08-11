import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { Ticket, TicketStatus } from '@/types/ticket';
import {
  assignTicketDepartment,
  fetchTicketById,
  fetchTickets,
  mergeDuplicateTickets,
  reviewTicketCategory,
  updateTicketStatus,
} from '@/services/tickets';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { EmptyState } from '@/components/EmptyState';
import { TicketPhoto } from '@/components/TicketPhoto';
import { StatusBadge } from '@/components/StatusBadge';
import { PriorityBadge } from '@/components/PriorityBadge';
import { CategoryBadge } from '@/components/CategoryBadge';
import {
  formatCategory,
  formatCreatedDate,
  formatStatus,
  formatTicketAge,
  SUPPORTED_CATEGORY_OPTIONS,
} from '@/utils/labels';
import { DEPARTMENT_OPTIONS, formatDepartment, isKnownDepartmentId } from '@/utils/departments';
import { effectiveTicketCategory } from '@/utils/ticketCategory';
import { statusToModifier } from '@/utils/statusTheme';
import { getSelectableTicketStatuses } from '@/utils/statusTransitions';
import { TicketMap } from '@/components/TicketMap';
import { TicketTimeline } from '@/components/TicketTimeline';
import { buildGoogleMapsUrl, isPlottableTicket } from '@/utils/ticketLocation';
import { getStaffNextAction } from '@/utils/reportGuidance';
import { IconAlert, IconClock, IconDocument, IconLocation, IconWorkflow } from '@/components/icons';
import './TicketDetailPage.css';

type LoadState = 'loading' | 'success' | 'not-found' | 'error';

function formatDistanceMeters(distanceMeters: number): string {
  if (distanceMeters >= 1000) {
    return `${(distanceMeters / 1000).toFixed(1)} km away`;
  }

  return `${Math.round(distanceMeters)} m away`;
}

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const { session } = useStaffAuth();
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pendingStatus, setPendingStatus] = useState<TicketStatus | ''>('');
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categoryReviewError, setCategoryReviewError] = useState<string | null>(null);
  const [isSavingCategory, setIsSavingCategory] = useState(false);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('');
  const [departmentUpdateError, setDepartmentUpdateError] = useState<string | null>(null);
  const [departmentUpdateSuccess, setDepartmentUpdateSuccess] = useState<string | null>(null);
  const [isSavingDepartment, setIsSavingDepartment] = useState(false);
  const [mergeCandidates, setMergeCandidates] = useState<Ticket[]>([]);
  const [selectedDuplicateIds, setSelectedDuplicateIds] = useState<string[]>([]);
  const [mergeError, setMergeError] = useState<string | null>(null);
  const [isMerging, setIsMerging] = useState(false);

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
        setPendingStatus(data.status);
        setSelectedCategory(data.ai?.finalCategory ?? data.ai?.aiSuggestedCategory ?? '');
        setSelectedDepartmentId(data.departmentId ?? '');
        setDepartmentUpdateError(null);
        setDepartmentUpdateSuccess(null);
        setSelectedDuplicateIds([]);
        setMergeError(null);
        setLoadState('success');

        try {
          // Use the effective category (final -> AI suggestion -> classified
          // category) so pending tickets never match everything.
          const ticketCategory = effectiveTicketCategory(data);
          const tickets = ticketCategory === null ? [] : await fetchTickets();
          if (!cancelled) {
            setMergeCandidates(
              tickets.filter(
                (candidate) =>
                  candidate.ticketId !== data.ticketId &&
                  !candidate.duplicateGroupId &&
                  effectiveTicketCategory(candidate) === ticketCategory,
              ),
            );
          }
        } catch {
          if (!cancelled) {
            setMergeCandidates([]);
          }
        }
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
      setPendingStatus(updatedTicket.status);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to update ticket status.';
      setStatusUpdateError(message);
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleApplyStatus = async () => {
    if (!pendingStatus) {
      return;
    }
    await handleStatusChange(pendingStatus);
  };

  const handleCategoryReview = async (finalCategory: string) => {
    if (!ticket) {
      return;
    }

    if (!SUPPORTED_CATEGORY_OPTIONS.some((category) => category === finalCategory)) {
      setCategoryReviewError('Select a supported category before saving.');
      return;
    }

    setSelectedCategory(finalCategory);
    setIsSavingCategory(true);
    setCategoryReviewError(null);

    try {
      const updatedTicket = await reviewTicketCategory(ticket.ticketId, { finalCategory });

      if (!updatedTicket) {
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      setTicket(updatedTicket);
      setSelectedCategory(updatedTicket.ai?.finalCategory ?? finalCategory);
      setSelectedDepartmentId(updatedTicket.departmentId ?? '');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to save the category review.';
      setCategoryReviewError(message);
    } finally {
      setIsSavingCategory(false);
    }
  };

  const handleDepartmentAssignment = async (departmentId: string) => {
    if (!ticket) {
      return;
    }

    if (!isKnownDepartmentId(departmentId)) {
      setDepartmentUpdateError('Select a department from the catalog before saving.');
      setDepartmentUpdateSuccess(null);
      return;
    }

    if (departmentId === ticket.departmentId) {
      return;
    }

    const previousDepartmentId = ticket.departmentId ?? '';
    setSelectedDepartmentId(departmentId);
    setIsSavingDepartment(true);
    setDepartmentUpdateError(null);
    setDepartmentUpdateSuccess(null);

    try {
      const updatedTicket = await assignTicketDepartment(ticket.ticketId, {
        departmentId,
        updatedBy: session?.username,
      });

      if (!updatedTicket) {
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      setTicket(updatedTicket);
      setSelectedDepartmentId(updatedTicket.departmentId ?? departmentId);
      setDepartmentUpdateSuccess('Department assignment updated.');
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Unable to update the ticket department.';
      setDepartmentUpdateError(message);
      setSelectedDepartmentId(previousDepartmentId);
      setDepartmentUpdateSuccess(null);
    } finally {
      setIsSavingDepartment(false);
    }
  };

  const toggleDuplicateSelection = (candidateId: string) => {
    setSelectedDuplicateIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );
    setMergeError(null);
  };

  const handleMergeDuplicates = async () => {
    if (!ticket) {
      return;
    }

    if (selectedDuplicateIds.length === 0) {
      setMergeError('Select at least one duplicate ticket to merge.');
      return;
    }

    setIsMerging(true);
    setMergeError(null);

    try {
      const updatedTicket = await mergeDuplicateTickets({
        canonicalTicketId: ticket.ticketId,
        duplicateTicketIds: selectedDuplicateIds,
      });

      if (!updatedTicket) {
        setMergeError('One or more selected tickets were not found.');
        return;
      }

      setTicket(updatedTicket);
      setSelectedDuplicateIds([]);
      setMergeCandidates((current) =>
        current.filter((candidate) => !selectedDuplicateIds.includes(candidate.ticketId)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to merge duplicate tickets.';
      setMergeError(message);
    } finally {
      setIsMerging(false);
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
            {/* 1. HEADER — what, urgency, state, ownership at a glance */}
            <header
              className={`ticket-detail__hero ticket-detail__hero--${statusToModifier(ticket.status)}`}
            >
              <div className="ticket-detail__hero-main">
                <div className="ticket-detail__hero-titles">
                  <h1 className="ticket-detail__hero-title">{ticket.ticketNumber}</h1>
                  <p className="ticket-detail__hero-sub">
                    Tracking code <strong>{ticket.trackingCode}</strong>
                  </p>
                </div>
                <div className="ticket-detail__hero-badges">
                  <CategoryBadge category={ticket.category} />
                  <StatusBadge status={ticket.status} />
                  <PriorityBadge priority={ticket.priority} />
                  {ticket.sla && ticket.sla.state !== 'unavailable' && (
                    <span className="ticket-detail__badge">
                      SLA: {ticket.sla.state.replace('_', ' ')}
                    </span>
                  )}
                </div>
              </div>

              <dl className="ticket-detail__hero-meta">
                <div className="ticket-detail__hero-meta-item">
                  <dt>Age</dt>
                  <dd>{formatTicketAge(ticket.createdAt)} old</dd>
                </div>
                <div className="ticket-detail__hero-meta-item">
                  <dt>Reported</dt>
                  <dd>
                    <time dateTime={ticket.createdAt}>{formatCreatedDate(ticket.createdAt)}</time>
                  </dd>
                </div>
                <div className="ticket-detail__hero-meta-item">
                  <dt>Department</dt>
                  <dd>{ticket.departmentName ?? formatDepartment(ticket.departmentId)}</dd>
                </div>
                <div className="ticket-detail__hero-meta-item ticket-detail__hero-meta-item--ref">
                  <dt>Internal ref</dt>
                  <dd
                    className="ticket-detail__mono ticket-detail__mono--truncate"
                    title={ticket.ticketId}
                  >
                    {ticket.ticketId}
                  </dd>
                </div>
              </dl>
            </header>

            {/* 2. NEXT ACTION — the single most important instruction for staff */}
            <section className="ticket-detail__next-action" aria-labelledby="next-action-heading">
              <span className="ticket-detail__next-action-icon" aria-hidden="true">
                <IconWorkflow />
              </span>
              <div className="ticket-detail__next-action-body">
                <h2 id="next-action-heading" className="ticket-detail__next-action-title">
                  Next action
                </h2>
                <p className="ticket-detail__next-action-text">
                  {getStaffNextAction(ticket.status)}
                </p>
              </div>
            </section>

            {/* 3. EVIDENCE — citizen-submitted facts: description, photo, location */}
            <section className="ticket-detail__section" aria-labelledby="evidence-heading">
              <h2 id="evidence-heading" className="ticket-detail__section-heading">
                <span className="ticket-detail__section-icon" aria-hidden="true">
                  <IconDocument />
                </span>
                Evidence
              </h2>

              <div className="ticket-detail__evidence-grid">
                <div className="ticket-detail__evidence-photo">
                  <TicketPhoto
                    imageObjectKey={ticket.imageObjectKey}
                    imageUrl={ticket.imageUrl}
                    category={ticket.category}
                    alt={`Report photo for ${ticket.ticketNumber}`}
                  />
                </div>

                <div
                  className="ticket-detail__card ticket-detail__card--description"
                  aria-labelledby="ticket-description-heading"
                >
                  <h3 id="ticket-description-heading" className="ticket-detail__card-title">
                    Citizen description
                  </h3>
                  <p className="ticket-detail__description">{ticket.description}</p>
                </div>
              </div>

              <div className="ticket-detail__card ticket-detail__card--location">
                <h3 className="ticket-detail__card-title">
                  <span className="ticket-detail__card-title-icon" aria-hidden="true">
                    <IconLocation />
                  </span>
                  Location
                </h3>
                <p className="ticket-detail__location-text">
                  {ticket.location.addressText.trim() || 'No address provided'}
                </p>
                {isPlottableTicket(ticket) ? (
                  <>
                    <p className="ticket-detail__coordinates">
                      {ticket.location.latitude.toFixed(5)}, {ticket.location.longitude.toFixed(5)}
                      <span className="ticket-detail__location-source">
                        {' '}
                        · {ticket.location.source}
                      </span>
                    </p>
                    <a
                      className="ticket-detail__maps-link"
                      href={buildGoogleMapsUrl(ticket.location.latitude, ticket.location.longitude)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Open in Google Maps
                    </a>
                    <TicketMap tickets={[ticket]} variant="detail" />
                  </>
                ) : (
                  <p className="ticket-detail__location-unavailable">
                    No valid map coordinates are available for this ticket.
                  </p>
                )}
              </div>
            </section>

            {/* 4. AI ASSISTANCE — clearly separated, non-authoritative machine output */}
            <section
              className="ticket-detail__section ticket-detail__section--ai"
              aria-labelledby="ai-heading"
            >
              <div className="ticket-detail__ai-heading-row">
                <h2 id="ai-heading" className="ticket-detail__section-heading">
                  <span className="ticket-detail__section-icon" aria-hidden="true">
                    <IconAlert />
                  </span>
                  AI Assistance
                </h2>
                <p className="ticket-detail__ai-disclaimer">
                  AI-generated — not ground truth. Staff must verify before acting.
                </p>
              </div>

              <div
                className="ticket-detail__card ticket-detail__card--ai-category"
                aria-labelledby="category-review-heading"
              >
                <div className="ticket-detail__category-review-heading">
                  <div>
                    <p className="ticket-detail__eyebrow">Staff review</p>
                    <h3 id="category-review-heading" className="ticket-detail__card-title">
                      AI category recommendation
                    </h3>
                  </div>
                  {ticket.ai?.finalCategory && (
                    <span className="ticket-detail__review-status">Reviewed</span>
                  )}
                </div>

                {ticket.ai?.aiProcessingStatus === 'pending' && (
                  <p className="ticket-detail__review-notice" role="status">
                    AI processing is still in progress. Category review will be available when it
                    finishes.
                  </p>
                )}

                {ticket.ai?.aiProcessingStatus === 'failed' && !ticket.ai.aiSuggestedCategory && (
                  <p
                    className="ticket-detail__review-notice ticket-detail__review-notice--warning"
                    role="status"
                  >
                    AI could not recommend a category. Select the correct category manually.
                  </p>
                )}

                {ticket.ai?.aiSuggestedCategory && (
                  <div className="ticket-detail__suggestion">
                    <div className="ticket-detail__suggestion-label">AI suggestion</div>
                    <CategoryBadge category={ticket.ai.aiSuggestedCategory} />
                    {ticket.ai.aiCategoryExplanation && <p>{ticket.ai.aiCategoryExplanation}</p>}
                    {ticket.ai.aiConfidence !== undefined && (
                      <span className="ticket-detail__confidence">
                        Confidence {Math.round(ticket.ai.aiConfidence * 100)}%
                      </span>
                    )}
                  </div>
                )}

                {ticket.ai?.finalCategory && (
                  <div className="ticket-detail__review-result" role="status">
                    <span>Final category</span>
                    <CategoryBadge category={ticket.ai.finalCategory} />
                    {ticket.ai.categoryReviewedAt && (
                      <small>
                        Reviewed
                        {ticket.ai.categoryReviewedBy ? ` by ${ticket.ai.categoryReviewedBy}` : ''}
                        {' on '}
                        <time dateTime={ticket.ai.categoryReviewedAt}>
                          {formatCreatedDate(ticket.ai.categoryReviewedAt)}
                        </time>
                      </small>
                    )}
                  </div>
                )}

                <div className="ticket-detail__control-row">
                  <label htmlFor="category-review-select">Final category</label>
                  <select
                    id="category-review-select"
                    className="ticket-detail__control-select"
                    value={selectedCategory}
                    onChange={(event) => {
                      setSelectedCategory(event.target.value);
                      setCategoryReviewError(null);
                    }}
                    disabled={isSavingCategory || ticket.ai?.aiProcessingStatus === 'pending'}
                  >
                    <option value="">Select a category</option>
                    {SUPPORTED_CATEGORY_OPTIONS.map((category) => (
                      <option key={category} value={category}>
                        {formatCategory(category)}
                      </option>
                    ))}
                  </select>

                  <div className="ticket-detail__control-buttons">
                    {ticket.ai?.aiSuggestedCategory && (
                      <button
                        type="button"
                        className="ticket-detail__review-button ticket-detail__review-button--secondary"
                        onClick={() =>
                          void handleCategoryReview(ticket.ai?.aiSuggestedCategory ?? '')
                        }
                        disabled={
                          isSavingCategory ||
                          ticket.ai.aiProcessingStatus === 'pending' ||
                          ticket.ai.finalCategory === ticket.ai.aiSuggestedCategory
                        }
                      >
                        Accept AI suggestion
                      </button>
                    )}
                    <button
                      type="button"
                      className="ticket-detail__review-button"
                      onClick={() => void handleCategoryReview(selectedCategory)}
                      disabled={
                        isSavingCategory ||
                        ticket.ai?.aiProcessingStatus === 'pending' ||
                        !selectedCategory
                      }
                    >
                      {isSavingCategory ? 'Saving category...' : 'Save final category'}
                    </button>
                  </div>
                </div>

                {categoryReviewError && (
                  <p className="ticket-detail__status-error" role="alert">
                    {categoryReviewError}
                  </p>
                )}
              </div>

              {(ticket.ai?.urgencyScore !== undefined || ticket.ai?.urgencyReason) && (
                <div className="ticket-detail__card ticket-detail__card--ai-urgency">
                  <h3 className="ticket-detail__card-title">AI urgency assessment</h3>
                  <dl className="ticket-detail__meta-list">
                    {ticket.ai?.urgencyScore !== undefined && (
                      <div className="ticket-detail__meta-row">
                        <dt>Urgency score</dt>
                        <dd>
                          <strong>{ticket.ai.urgencyScore}/100</strong>
                        </dd>
                      </div>
                    )}
                    {ticket.ai?.urgencyReason && (
                      <div className="ticket-detail__meta-row ticket-detail__meta-row--stacked">
                        <dt>Urgency reason</dt>
                        <dd>
                          <span>{ticket.ai.urgencyReason}</span>
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              )}
            </section>

            {/* 5. MUNICIPAL ACTIONS — authoritative staff decisions */}
            <section className="ticket-detail__section" aria-labelledby="actions-heading">
              <h2 id="actions-heading" className="ticket-detail__section-heading">
                <span className="ticket-detail__section-icon" aria-hidden="true">
                  <IconWorkflow />
                </span>
                Municipal actions
              </h2>

              <div className="ticket-detail__actions-grid">
                <div className="ticket-detail__card ticket-detail__card--status">
                  <h3 className="ticket-detail__card-title">Status</h3>
                  <p className="ticket-detail__card-hint">
                    Select a new status, then apply it. Status never changes until you confirm.
                  </p>

                  <div className="ticket-detail__control-row">
                    <label htmlFor="status-update-select">New status</label>
                    <select
                      id="status-update-select"
                      className="ticket-detail__control-select"
                      value={pendingStatus || ticket.status}
                      onChange={(event) => {
                        setPendingStatus(event.target.value as TicketStatus);
                        setStatusUpdateError(null);
                      }}
                      disabled={isUpdatingStatus}
                    >
                      {getSelectableTicketStatuses(ticket.status).map((status) => (
                        <option key={status} value={status}>
                          {formatStatus(status)}
                        </option>
                      ))}
                    </select>

                    <div className="ticket-detail__control-buttons">
                      <button
                        type="button"
                        className="ticket-detail__review-button"
                        onClick={() => void handleApplyStatus()}
                        disabled={
                          isUpdatingStatus || !pendingStatus || pendingStatus === ticket.status
                        }
                      >
                        {isUpdatingStatus ? 'Applying...' : 'Apply status change'}
                      </button>
                    </div>
                  </div>

                  {isUpdatingStatus && (
                    <p className="ticket-detail__status-message" role="status">
                      Saving...
                    </p>
                  )}
                  {statusUpdateError && (
                    <p className="ticket-detail__status-error" role="alert">
                      {statusUpdateError}
                    </p>
                  )}
                </div>

                <div className="ticket-detail__card ticket-detail__card--department">
                  <h3 className="ticket-detail__card-title">Department</h3>
                  <div className="ticket-detail__department-current">
                    <span className="ticket-detail__department">
                      {ticket.departmentName ?? formatDepartment(ticket.departmentId)}
                    </span>
                    {ticket.ai?.suggestedDepartmentId &&
                      ticket.ai.suggestedDepartmentId !== ticket.departmentId && (
                        <small className="ticket-detail__suggested-department">
                          Suggested: {formatDepartment(ticket.ai.suggestedDepartmentId)}
                        </small>
                      )}
                  </div>

                  <div className="ticket-detail__control-row">
                    <label htmlFor="department-assign-select">Assigned department</label>
                    <select
                      id="department-assign-select"
                      className="ticket-detail__control-select"
                      value={selectedDepartmentId}
                      onChange={(event) => {
                        setSelectedDepartmentId(event.target.value);
                        setDepartmentUpdateError(null);
                        setDepartmentUpdateSuccess(null);
                      }}
                      disabled={isSavingDepartment}
                    >
                      <option value="">Select a department</option>
                      {DEPARTMENT_OPTIONS.map((department) => (
                        <option key={department.departmentId} value={department.departmentId}>
                          {department.name}
                        </option>
                      ))}
                    </select>

                    <div className="ticket-detail__control-buttons">
                      {ticket.ai?.suggestedDepartmentId &&
                        ticket.ai.suggestedDepartmentId !== ticket.departmentId && (
                          <button
                            type="button"
                            className="ticket-detail__review-button ticket-detail__review-button--secondary"
                            onClick={() =>
                              void handleDepartmentAssignment(
                                ticket.ai?.suggestedDepartmentId ?? '',
                              )
                            }
                            disabled={isSavingDepartment || !ticket.ai?.suggestedDepartmentId}
                          >
                            Accept suggested department
                          </button>
                        )}
                      <button
                        type="button"
                        className="ticket-detail__review-button"
                        onClick={() => void handleDepartmentAssignment(selectedDepartmentId)}
                        disabled={
                          isSavingDepartment ||
                          !selectedDepartmentId ||
                          selectedDepartmentId === (ticket.departmentId ?? '')
                        }
                      >
                        {isSavingDepartment ? 'Saving department...' : 'Save department'}
                      </button>
                    </div>
                  </div>

                  {isSavingDepartment && (
                    <p className="ticket-detail__status-message" role="status">
                      Saving department assignment...
                    </p>
                  )}
                  {!isSavingDepartment && departmentUpdateSuccess && (
                    <p className="ticket-detail__status-message" role="status">
                      {departmentUpdateSuccess}
                    </p>
                  )}
                  {departmentUpdateError && (
                    <p className="ticket-detail__status-error" role="alert">
                      {departmentUpdateError}
                    </p>
                  )}
                  {ticket.updatedBy && ticket.departmentId && (
                    <small className="ticket-detail__department-actor">
                      Last updated by {ticket.updatedBy}
                      {ticket.updatedAt ? (
                        <>
                          {' on '}
                          <time dateTime={ticket.updatedAt}>
                            {formatCreatedDate(ticket.updatedAt)}
                          </time>
                        </>
                      ) : null}
                    </small>
                  )}
                </div>
              </div>

              <div className="ticket-detail__card ticket-detail__card--duplicates">
                <h3 className="ticket-detail__card-title">Duplicate group</h3>

                <div className="ticket-detail__suggestions">
                  <h4 className="ticket-detail__subsection-title">Possible duplicates</h4>
                  {(ticket.duplicateSuggestions ?? []).length === 0 ? (
                    <p className="ticket-detail__merge-empty">
                      {effectiveTicketCategory(ticket) === null
                        ? 'Duplicate suggestions are available once this ticket is classified.'
                        : 'No possible duplicate tickets found.'}
                    </p>
                  ) : (
                    <ul className="ticket-detail__suggestion-list">
                      {(ticket.duplicateSuggestions ?? []).map((suggestion) => (
                        <li key={suggestion.ticketId} className="ticket-detail__suggestion-item">
                          <div className="ticket-detail__suggestion-main">
                            <Link
                              to={`/tickets/${suggestion.ticketId}`}
                              className="ticket-detail__suggestion-link"
                            >
                              {suggestion.ticketNumber ?? suggestion.ticketId}
                            </Link>
                            <span>{formatDistanceMeters(suggestion.distanceMeters)}</span>
                          </div>
                          <div className="ticket-detail__suggestion-meta">
                            <StatusBadge status={suggestion.status} />
                            <CategoryBadge category={suggestion.category} />
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {ticket.duplicateGroupId && (
                  <div className="ticket-detail__group-summary" role="status">
                    <p>
                      This ticket is grouped
                      {ticket.duplicateGroup?.canonicalTicketId === ticket.ticketId
                        ? ' as the main report'
                        : ''}
                      .
                    </p>
                    {ticket.duplicateGroup?.ticketIds && (
                      <ul className="ticket-detail__group-links">
                        {ticket.duplicateGroup.ticketIds.map((memberId) => (
                          <li key={memberId}>
                            {memberId === ticket.ticketId ? (
                              <span>
                                {memberId === ticket.duplicateGroup?.canonicalTicketId
                                  ? 'Main: '
                                  : ''}
                                Current ticket
                              </span>
                            ) : (
                              <Link to={`/tickets/${memberId}`}>
                                {memberId === ticket.duplicateGroup?.canonicalTicketId
                                  ? 'Main: '
                                  : ''}
                                {memberId}
                              </Link>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {ticket.duplicateGroup?.canonicalTicketId !== ticket.ticketId && (
                      <p className="ticket-detail__merge-help">
                        Add further duplicates from the main ticket.
                      </p>
                    )}
                  </div>
                )}

                {(!ticket.duplicateGroupId ||
                  ticket.duplicateGroup?.canonicalTicketId === ticket.ticketId) && (
                  <div className="ticket-detail__merge-controls">
                    {effectiveTicketCategory(ticket) === null ? (
                      <p className="ticket-detail__merge-empty">
                        This ticket has no reviewed or AI-suggested category yet. Merging is
                        available once it is classified.
                      </p>
                    ) : (
                      <>
                        <p className="ticket-detail__merge-help">
                          {ticket.duplicateGroupId
                            ? 'Add more same-category tickets to this duplicate group.'
                            : 'Choose other same-category tickets to link under this main report.'}
                        </p>
                        {mergeCandidates.length === 0 ? (
                          <p className="ticket-detail__merge-empty">
                            No ungrouped same-category tickets are available to merge.
                          </p>
                        ) : (
                          <ul className="ticket-detail__merge-candidates">
                            {mergeCandidates.map((candidate) => (
                              <li key={candidate.ticketId}>
                                <label>
                                  <input
                                    type="checkbox"
                                    checked={selectedDuplicateIds.includes(candidate.ticketId)}
                                    onChange={() => toggleDuplicateSelection(candidate.ticketId)}
                                    disabled={isMerging}
                                  />
                                  <span>
                                    {candidate.ticketNumber}
                                    <small>{candidate.location.addressText}</small>
                                  </span>
                                </label>
                              </li>
                            ))}
                          </ul>
                        )}
                        <button
                          type="button"
                          className="ticket-detail__review-button"
                          onClick={() => void handleMergeDuplicates()}
                          disabled={isMerging || mergeCandidates.length === 0}
                        >
                          {isMerging ? 'Merging...' : 'Merge selected as duplicates'}
                        </button>
                        {mergeError && (
                          <p className="ticket-detail__status-error" role="alert">
                            {mergeError}
                          </p>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </section>

            {/* 6. HISTORY — full audit trail */}
            <section className="ticket-detail__section" aria-labelledby="history-heading">
              <h2 id="history-heading" className="ticket-detail__section-heading">
                <span className="ticket-detail__section-icon" aria-hidden="true">
                  <IconClock />
                </span>
                History
              </h2>
              <div className="ticket-detail__card ticket-detail__card--history">
                <dl className="ticket-detail__meta-list ticket-detail__timeline-summary">
                  <div className="ticket-detail__meta-row">
                    <dt>Created</dt>
                    <dd>
                      <time dateTime={ticket.createdAt}>{formatCreatedDate(ticket.createdAt)}</time>
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
                <TicketTimeline history={ticket.statusHistory} variant="staff" />
              </div>
            </section>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

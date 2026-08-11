import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import type { Ticket, TicketPriority, TicketStatus } from '@/types/ticket';
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
import { TicketMap } from '@/components/TicketMap';
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
import { buildGoogleMapsUrl, isPlottableTicket } from '@/utils/ticketLocation';
import { getStaffNextAction } from '@/utils/reportGuidance';
import { getTicketImageUrl } from '@/utils/ticketImage';
import { IconImage, IconLocation, IconSparkles, IconWorkflow } from '@/components/icons';
import {
  parseTicketDetailSection,
  TICKET_DETAIL_SECTION_LABELS,
  TICKET_DETAIL_SECTION_PARAM,
  TICKET_DETAIL_SECTIONS,
  ticketDetailPanelId,
  ticketDetailTabId,
  type TicketDetailSection,
} from './ticketDetail/sections';
import { buildActivityTimeline } from './ticketDetail/activityTimeline';
import {
  describeExcerpt,
  distanceMetersBetween,
  formatDistanceMeters,
  toDuplicateComparison,
  type DuplicateComparison,
} from './ticketDetail/duplicateComparison';
import { formatUrgencySummary } from './ticketDetail/urgency';
import './TicketDetailPage.css';

type LoadState = 'loading' | 'success' | 'not-found' | 'error';

type ComparisonState =
  | { status: 'loading' }
  | { status: 'ready'; data: DuplicateComparison }
  | { status: 'error'; message: string };

type DuplicateCandidate = {
  ticketId: string;
  ticketNumber: string;
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  description?: string;
  createdAt?: string;
  addressText?: string;
  distanceMeters?: number;
  imageObjectKey?: string;
  imageUrl?: string;
  /** Surfaced by the automated duplicate detector rather than staff browsing. */
  suggested: boolean;
  /** Ungrouped and same effective category, so the merge mutation would accept it. */
  mergeable: boolean;
};

/** Candidate lists stay bounded; staff narrow them with the filter instead. */
const MAX_DUPLICATE_CANDIDATES = 20;

function CandidateThumb({
  ticketNumber,
  category,
  imageObjectKey,
  imageUrl,
}: {
  ticketNumber: string;
  category: string;
  imageObjectKey?: string;
  imageUrl?: string;
}) {
  const resolvedUrl =
    imageObjectKey && imageObjectKey !== 'unavailable'
      ? getTicketImageUrl(imageObjectKey, category, imageUrl)
      : null;

  if (!resolvedUrl) {
    return (
      <span
        className="ticket-detail__thumb ticket-detail__thumb--empty"
        role="img"
        aria-label={`No photo available for ${ticketNumber}`}
      >
        <IconImage className="ticket-detail__thumb-icon" />
      </span>
    );
  }

  return (
    <img
      className="ticket-detail__thumb"
      src={resolvedUrl}
      alt={`Report photo for ${ticketNumber}`}
    />
  );
}

function ComparisonColumn({
  heading,
  eyebrow,
  data,
}: {
  heading: string;
  eyebrow: string;
  data: DuplicateComparison;
}) {
  return (
    <div className="ticket-detail__comparison-column">
      <p className="ticket-detail__eyebrow">{eyebrow}</p>
      <h5 className="ticket-detail__comparison-title">{heading}</h5>
      <TicketPhoto
        imageObjectKey={data.imageObjectKey}
        imageUrl={data.imageUrl}
        category={data.category}
        alt={`Report photo for ${data.ticketNumber}`}
      />
      <p className="ticket-detail__comparison-description">{data.description}</p>
      <dl className="ticket-detail__comparison-facts">
        <div>
          <dt>Status</dt>
          <dd>
            <StatusBadge status={data.status} />
          </dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>
            <CategoryBadge category={data.category} />
          </dd>
        </div>
        <div>
          <dt>Priority</dt>
          <dd>
            <PriorityBadge priority={data.priority} />
          </dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd>
            <time dateTime={data.createdAt}>{formatCreatedDate(data.createdAt)}</time>
          </dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>{data.location.addressText || 'No address provided'}</dd>
        </div>
      </dl>
    </div>
  );
}

export function TicketDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  const { session } = useStaffAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeSection = parseTicketDetailSection(searchParams.get(TICKET_DETAIL_SECTION_PARAM));

  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

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
  const [expandedDuplicateIds, setExpandedDuplicateIds] = useState<string[]>([]);
  const [comparisons, setComparisons] = useState<Record<string, ComparisonState>>({});
  const [candidateFilter, setCandidateFilter] = useState('');
  const [isMergeDialogOpen, setIsMergeDialogOpen] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);
  const [isMerging, setIsMerging] = useState(false);

  const loadedTicketRef = useRef<Ticket | null>(null);
  /** Guards against a second request for a candidate already fetched this session. */
  const requestedComparisonsRef = useRef<Set<string>>(new Set());
  const tabRefs = useRef<Partial<Record<TicketDetailSection, HTMLButtonElement | null>>>({});
  const confirmMergeRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!ticketId) {
      setLoadState('not-found');
      return;
    }

    const requestedTicketId = ticketId;
    let cancelled = false;

    async function loadTicket() {
      // Keep already-rendered content visible while an explicit refresh runs.
      const hasLoadedTicket = loadedTicketRef.current?.ticketId === requestedTicketId;
      if (hasLoadedTicket) {
        setIsRefreshing(true);
      } else {
        setLoadState('loading');
      }
      setErrorMessage(null);
      requestedComparisonsRef.current = new Set();
      setComparisons({});
      setExpandedDuplicateIds([]);
      setIsMergeDialogOpen(false);

      try {
        const data = await fetchTicketById(requestedTicketId);
        if (cancelled) {
          return;
        }

        if (!data) {
          loadedTicketRef.current = null;
          setTicket(null);
          setLoadState('not-found');
          return;
        }

        loadedTicketRef.current = data;
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
          if (loadedTicketRef.current?.ticketId !== requestedTicketId) {
            setLoadState('error');
          }
        }
      } finally {
        if (!cancelled) {
          setIsRefreshing(false);
        }
      }
    }

    void loadTicket();

    return () => {
      cancelled = true;
    };
    // Section changes are deliberately absent: the ticket loads once per route
    // entry and only an explicit refresh revalidates it.
  }, [ticketId, refreshToken]);

  const selectSection = useCallback(
    (section: TicketDetailSection) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set(TICKET_DETAIL_SECTION_PARAM, section);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const total = TICKET_DETAIL_SECTIONS.length;
    let nextIndex: number | null = null;

    if (event.key === 'ArrowRight') {
      nextIndex = (index + 1) % total;
    } else if (event.key === 'ArrowLeft') {
      nextIndex = (index - 1 + total) % total;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = total - 1;
    }

    if (nextIndex === null) {
      return;
    }

    event.preventDefault();
    const nextSection = TICKET_DETAIL_SECTIONS[nextIndex];
    selectSection(nextSection);
    tabRefs.current[nextSection]?.focus();
  };

  const handleRefresh = () => {
    setRefreshToken((current) => current + 1);
  };

  const handleStatusChange = async (status: TicketStatus) => {
    if (!ticket || status === ticket.status) {
      return;
    }

    setIsUpdatingStatus(true);
    setStatusUpdateError(null);

    try {
      const updatedTicket = await updateTicketStatus(ticket.ticketId, status);

      if (!updatedTicket) {
        loadedTicketRef.current = null;
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      loadedTicketRef.current = updatedTicket;
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
        loadedTicketRef.current = null;
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      loadedTicketRef.current = updatedTicket;
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
        loadedTicketRef.current = null;
        setLoadState('not-found');
        setTicket(null);
        return;
      }

      loadedTicketRef.current = updatedTicket;
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

  const loadComparison = useCallback(async (candidateId: string) => {
    requestedComparisonsRef.current.add(candidateId);
    setComparisons((current) => ({ ...current, [candidateId]: { status: 'loading' } }));

    try {
      const candidateTicket = await fetchTicketById(candidateId);
      if (!candidateTicket) {
        requestedComparisonsRef.current.delete(candidateId);
        setComparisons((current) => ({
          ...current,
          [candidateId]: {
            status: 'error',
            message: 'This candidate ticket is no longer available.',
          },
        }));
        return;
      }

      setComparisons((current) => ({
        ...current,
        [candidateId]: { status: 'ready', data: toDuplicateComparison(candidateTicket) },
      }));
    } catch (error) {
      // Allow a retry for this candidate only; other rows stay untouched.
      requestedComparisonsRef.current.delete(candidateId);
      setComparisons((current) => ({
        ...current,
        [candidateId]: {
          status: 'error',
          message:
            error instanceof Error ? error.message : 'Unable to load the duplicate comparison.',
        },
      }));
    }
  }, []);

  const toggleCandidateExpanded = (candidateId: string) => {
    setExpandedDuplicateIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );

    if (!requestedComparisonsRef.current.has(candidateId)) {
      void loadComparison(candidateId);
    }
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

      loadedTicketRef.current = updatedTicket;
      setTicket(updatedTicket);
      setMergeCandidates((current) =>
        current.filter((candidate) => !selectedDuplicateIds.includes(candidate.ticketId)),
      );
      setExpandedDuplicateIds((current) =>
        current.filter((id) => !selectedDuplicateIds.includes(id)),
      );
      setSelectedDuplicateIds([]);
      setIsMergeDialogOpen(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to merge duplicate tickets.';
      setMergeError(message);
      setIsMergeDialogOpen(false);
    } finally {
      setIsMerging(false);
    }
  };

  useEffect(() => {
    if (isMergeDialogOpen) {
      confirmMergeRef.current?.focus();
    }
  }, [isMergeDialogOpen]);

  const currentComparison = useMemo(
    () => (ticket ? toDuplicateComparison(ticket) : null),
    [ticket],
  );

  const duplicateCandidates = useMemo<DuplicateCandidate[]>(() => {
    if (!ticket) {
      return [];
    }

    const mergeCandidateById = new Map(
      mergeCandidates.map((candidate) => [candidate.ticketId, candidate]),
    );
    const candidates: DuplicateCandidate[] = [];
    const seen = new Set<string>();

    for (const suggestion of ticket.duplicateSuggestions ?? []) {
      const enriched = mergeCandidateById.get(suggestion.ticketId);
      candidates.push({
        ticketId: suggestion.ticketId,
        ticketNumber: suggestion.ticketNumber ?? enriched?.ticketNumber ?? suggestion.ticketId,
        status: enriched?.status ?? suggestion.status,
        category: enriched
          ? (effectiveTicketCategory(enriched) ?? enriched.category)
          : suggestion.category,
        priority: enriched?.priority ?? null,
        description: enriched?.description,
        createdAt: enriched?.createdAt,
        addressText: enriched?.location.addressText,
        distanceMeters: suggestion.distanceMeters,
        imageObjectKey: enriched?.imageObjectKey,
        imageUrl: enriched?.imageUrl,
        suggested: true,
        mergeable: Boolean(enriched),
      });
      seen.add(suggestion.ticketId);
    }

    for (const candidate of mergeCandidates) {
      if (seen.has(candidate.ticketId)) {
        continue;
      }
      const distance = distanceMetersBetween(ticket.location, candidate.location);
      candidates.push({
        ticketId: candidate.ticketId,
        ticketNumber: candidate.ticketNumber,
        status: candidate.status,
        category: effectiveTicketCategory(candidate) ?? candidate.category,
        priority: candidate.priority,
        description: candidate.description,
        createdAt: candidate.createdAt,
        addressText: candidate.location.addressText,
        distanceMeters: distance ?? undefined,
        imageObjectKey: candidate.imageObjectKey,
        imageUrl: candidate.imageUrl,
        suggested: false,
        mergeable: true,
      });
    }

    return candidates;
  }, [ticket, mergeCandidates]);

  const filteredCandidates = useMemo(() => {
    const query = candidateFilter.trim().toLowerCase();
    if (!query) {
      return duplicateCandidates;
    }
    return duplicateCandidates.filter((candidate) =>
      [candidate.ticketNumber, candidate.description, candidate.addressText]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(query),
    );
  }, [duplicateCandidates, candidateFilter]);

  const visibleCandidates = filteredCandidates.slice(0, MAX_DUPLICATE_CANDIDATES);
  const activityEvents = useMemo(() => buildActivityTimeline(ticket), [ticket]);

  const suggestionCount = ticket?.duplicateSuggestions?.length ?? 0;
  const effectiveCategory = ticket ? effectiveTicketCategory(ticket) : null;
  const isCanonicalTicket =
    !!ticket &&
    (!ticket.duplicateGroupId || ticket.duplicateGroup?.canonicalTicketId === ticket.ticketId);
  const selectedCandidates = duplicateCandidates.filter((candidate) =>
    selectedDuplicateIds.includes(candidate.ticketId),
  );

  return (
    <DashboardLayout
      title="Ticket Details"
      subtitle={
        ticket
          ? `${ticket.ticketNumber} · ${formatStatus(ticket.status)}`
          : 'Municipal review workspace'
      }
    >
      <div className="ticket-detail-page">
        <Link to="/" className="ticket-detail-page__back">
          ← Back to ticket queue
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
            {/* Sticky summary: identity, state, and the one primary action. */}
            <header
              className={`ticket-detail__summary ticket-detail__summary--${statusToModifier(ticket.status)}`}
            >
              <div className="ticket-detail__summary-main">
                <div className="ticket-detail__summary-identity">
                  <h2 className="ticket-detail__summary-title">{ticket.ticketNumber}</h2>
                  <div className="ticket-detail__summary-badges">
                    <StatusBadge status={ticket.status} />
                    <PriorityBadge priority={ticket.priority} />
                    <CategoryBadge category={effectiveCategory ?? ticket.category} />
                  </div>
                </div>

                <div className="ticket-detail__summary-actions">
                  <button
                    type="button"
                    className="ticket-detail__primary-action"
                    onClick={() => selectSection('review')}
                  >
                    Review & update ticket
                  </button>
                  <button
                    type="button"
                    className="ticket-detail__ghost-button"
                    onClick={handleRefresh}
                    disabled={isRefreshing}
                  >
                    {isRefreshing ? 'Refreshing…' : 'Refresh'}
                  </button>
                </div>
              </div>

              <dl className="ticket-detail__summary-meta">
                <div className="ticket-detail__summary-meta-item">
                  <dt>Age</dt>
                  <dd>{formatTicketAge(ticket.createdAt)} old</dd>
                </div>
                <div className="ticket-detail__summary-meta-item">
                  <dt>Department</dt>
                  <dd>{ticket.departmentName ?? formatDepartment(ticket.departmentId)}</dd>
                </div>
                <div className="ticket-detail__summary-meta-item">
                  <dt>Category</dt>
                  <dd>
                    {effectiveCategory
                      ? formatCategory(effectiveCategory)
                      : 'Pending classification'}
                  </dd>
                </div>
                {ticket.sla && ticket.sla.state !== 'unavailable' && (
                  <div className="ticket-detail__summary-meta-item">
                    <dt>SLA</dt>
                    <dd>{ticket.sla.state.replace(/_/g, ' ')}</dd>
                  </div>
                )}
              </dl>

              {isRefreshing && (
                <p className="ticket-detail__refresh-status" role="status">
                  Refreshing ticket…
                </p>
              )}
              {!isRefreshing && errorMessage && (
                <p className="ticket-detail__status-error" role="alert">
                  {errorMessage}
                </p>
              )}

              <details className="ticket-detail__technical">
                <summary>Technical details</summary>
                <dl className="ticket-detail__technical-list">
                  <div>
                    <dt>Tracking code</dt>
                    <dd className="ticket-detail__mono">{ticket.trackingCode}</dd>
                  </div>
                  <div>
                    <dt>Internal ticket ID</dt>
                    <dd className="ticket-detail__mono">{ticket.ticketId}</dd>
                  </div>
                  <div>
                    <dt>Evidence object key</dt>
                    <dd className="ticket-detail__mono">{ticket.imageObjectKey}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>
                      <time dateTime={ticket.createdAt}>{formatCreatedDate(ticket.createdAt)}</time>
                    </dd>
                  </div>
                  {ticket.updatedAt && (
                    <div>
                      <dt>Last updated</dt>
                      <dd>
                        <time dateTime={ticket.updatedAt}>
                          {formatCreatedDate(ticket.updatedAt)}
                        </time>
                      </dd>
                    </div>
                  )}
                </dl>
              </details>
            </header>

            <div
              className="ticket-detail__tabs"
              role="tablist"
              aria-label="Ticket workspace sections"
            >
              {TICKET_DETAIL_SECTIONS.map((section, index) => {
                const isActive = section === activeSection;
                return (
                  <button
                    key={section}
                    type="button"
                    role="tab"
                    id={ticketDetailTabId(section)}
                    aria-controls={ticketDetailPanelId(section)}
                    aria-selected={isActive}
                    aria-label={
                      section === 'duplicates' && suggestionCount > 0
                        ? `Duplicates, ${suggestionCount} possible duplicates`
                        : undefined
                    }
                    tabIndex={isActive ? 0 : -1}
                    ref={(element) => {
                      tabRefs.current[section] = element;
                    }}
                    className={`ticket-detail__tab${isActive ? ' ticket-detail__tab--active' : ''}`}
                    onClick={() => selectSection(section)}
                    onKeyDown={(event) => handleTabKeyDown(event, index)}
                  >
                    {TICKET_DETAIL_SECTION_LABELS[section]}
                    {section === 'duplicates' && suggestionCount > 0 && (
                      <span className="ticket-detail__tab-badge" aria-hidden="true">
                        {suggestionCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {activeSection === 'overview' && (
              <section
                id={ticketDetailPanelId('overview')}
                role="tabpanel"
                tabIndex={0}
                aria-labelledby={ticketDetailTabId('overview')}
                className="ticket-detail__panel"
              >
                <h3 className="sr-only">Overview</h3>

                <div className="ticket-detail__next-action">
                  <span className="ticket-detail__next-action-icon" aria-hidden="true">
                    <IconWorkflow />
                  </span>
                  <div>
                    <p className="ticket-detail__next-action-title">Next action</p>
                    <p className="ticket-detail__next-action-text">
                      {getStaffNextAction(ticket.status)}
                    </p>
                  </div>
                </div>

                <div className="ticket-detail__overview-grid">
                  <div className="ticket-detail__card">
                    <h4 className="ticket-detail__card-title">Citizen report</h4>
                    <p className="ticket-detail__description">{ticket.description}</p>
                    <div className="ticket-detail__overview-photo">
                      <TicketPhoto
                        imageObjectKey={ticket.imageObjectKey}
                        imageUrl={ticket.imageUrl}
                        category={effectiveCategory ?? ticket.category}
                        alt={`Report photo for ${ticket.ticketNumber}`}
                      />
                    </div>
                  </div>

                  <div className="ticket-detail__card">
                    <h4 className="ticket-detail__card-title">
                      <span className="ticket-detail__card-title-icon" aria-hidden="true">
                        <IconLocation />
                      </span>
                      Location
                    </h4>
                    <p className="ticket-detail__location-text">
                      {ticket.location.addressText.trim() || 'No address provided'}
                    </p>
                    {isPlottableTicket(ticket) ? (
                      <>
                        <p className="ticket-detail__coordinates">
                          {ticket.location.latitude.toFixed(5)},{' '}
                          {ticket.location.longitude.toFixed(5)}
                          <span className="ticket-detail__location-source">
                            {' '}
                            · {ticket.location.source}
                          </span>
                        </p>
                        <a
                          className="ticket-detail__maps-link"
                          href={buildGoogleMapsUrl(
                            ticket.location.latitude,
                            ticket.location.longitude,
                          )}
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
                </div>
              </section>
            )}

            {activeSection === 'review' && (
              <section
                id={ticketDetailPanelId('review')}
                role="tabpanel"
                tabIndex={0}
                aria-labelledby={ticketDetailTabId('review')}
                className="ticket-detail__panel"
              >
                <h3 className="sr-only">Review &amp; actions</h3>

                <p className="ticket-detail__ai-disclaimer">
                  <span className="ticket-detail__ai-icon" aria-hidden="true">
                    <IconSparkles />
                  </span>
                  AI-assisted fields are decision support only. Staff must verify them before
                  acting.
                </p>

                <div className="ticket-detail__card">
                  <h4 className="ticket-detail__card-title">Municipal actions</h4>
                  <p className="ticket-detail__card-hint">
                    Status and department never change until you save the change.
                  </p>

                  <div className="ticket-detail__actions-grid">
                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__eyebrow">Status</p>
                      <p className="ticket-detail__current-value">
                        Current: <StatusBadge status={ticket.status} />
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

                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__eyebrow">Department</p>
                      <div className="ticket-detail__department-current">
                        <span className="ticket-detail__department">
                          {ticket.departmentName ?? formatDepartment(ticket.departmentId)}
                        </span>
                        {ticket.ai?.suggestedDepartmentId &&
                          ticket.ai.suggestedDepartmentId !== ticket.departmentId && (
                            <small className="ticket-detail__suggested-department">
                              <span className="ticket-detail__ai-icon" aria-hidden="true">
                                <IconSparkles />
                              </span>
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
                </div>

                <div className="ticket-detail__card">
                  <div className="ticket-detail__card-heading-row">
                    <h4 className="ticket-detail__card-title">Category decision</h4>
                    <span className="ticket-detail__ai-chip">
                      <span className="ticket-detail__ai-icon" aria-hidden="true">
                        <IconSparkles />
                      </span>
                      AI-assisted
                    </span>
                    {ticket.ai?.finalCategory && (
                      <span className="ticket-detail__review-status">Reviewed</span>
                    )}
                  </div>

                  {!ticket.ai && (
                    <p className="ticket-detail__review-notice" role="status">
                      No AI analysis is available for this ticket. Select the correct category
                      manually.
                    </p>
                  )}

                  {ticket.ai?.aiProcessingStatus === 'pending' && (
                    <p className="ticket-detail__review-notice" role="status">
                      AI processing is still in progress. Category review will be available when it
                      finishes.
                    </p>
                  )}

                  {ticket.ai?.aiProcessingStatus === 'processing' && (
                    <p className="ticket-detail__review-notice" role="status">
                      AI processing is running. Suggestions may still change.
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
                      <span className="ticket-detail__suggestion-label">AI suggestion</span>
                      <CategoryBadge category={ticket.ai.aiSuggestedCategory} />
                      {ticket.ai.aiConfidence !== undefined && (
                        <span className="ticket-detail__confidence">
                          Confidence {Math.round(ticket.ai.aiConfidence * 100)}%
                        </span>
                      )}
                      {ticket.ai.aiCategoryExplanation && (
                        <p className="ticket-detail__rationale">
                          {ticket.ai.aiCategoryExplanation}
                        </p>
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
                          {ticket.ai.categoryReviewedBy
                            ? ` by ${ticket.ai.categoryReviewedBy}`
                            : ''}
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
                  <div className="ticket-detail__card ticket-detail__card--urgency">
                    <div className="ticket-detail__card-heading-row">
                      <h4 className="ticket-detail__card-title">Urgency</h4>
                      <span className="ticket-detail__ai-chip">
                        <span className="ticket-detail__ai-icon" aria-hidden="true">
                          <IconSparkles />
                        </span>
                        AI-assisted
                      </span>
                      {ticket.ai?.urgencyScore !== undefined && (
                        <span className="ticket-detail__urgency-summary">
                          {formatUrgencySummary(ticket.ai.urgencyScore)}
                        </span>
                      )}
                    </div>

                    {ticket.ai?.urgencyReason && (
                      <details className="ticket-detail__disclosure">
                        <summary>Why this score?</summary>
                        <p className="ticket-detail__rationale">{ticket.ai.urgencyReason}</p>
                      </details>
                    )}
                  </div>
                )}
              </section>
            )}

            {activeSection === 'duplicates' && (
              <section
                id={ticketDetailPanelId('duplicates')}
                role="tabpanel"
                tabIndex={0}
                aria-labelledby={ticketDetailTabId('duplicates')}
                className="ticket-detail__panel"
              >
                <h3 className="sr-only">Duplicates</h3>

                <div className="ticket-detail__card">
                  <h4 className="ticket-detail__card-title">Possible duplicates</h4>
                  <p className="ticket-detail__card-hint">
                    Suggested matches are automated hints, not confirmed duplicates. Compare the
                    evidence before merging.
                  </p>

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
                      {!isCanonicalTicket && (
                        <p className="ticket-detail__merge-help">
                          Add further duplicates from the main ticket.
                        </p>
                      )}
                    </div>
                  )}

                  {effectiveCategory === null ? (
                    <p className="ticket-detail__merge-empty">
                      This ticket has no reviewed or AI-suggested category yet. Duplicate
                      suggestions and merging are available once it is classified.
                    </p>
                  ) : duplicateCandidates.length === 0 ? (
                    <p className="ticket-detail__merge-empty">
                      No possible duplicate tickets found.
                    </p>
                  ) : (
                    <>
                      <div className="ticket-detail__candidate-toolbar">
                        <label htmlFor="duplicate-filter">Filter duplicate candidates</label>
                        <input
                          id="duplicate-filter"
                          type="search"
                          className="ticket-detail__filter-input"
                          value={candidateFilter}
                          onChange={(event) => setCandidateFilter(event.target.value)}
                          placeholder="Ticket number, description, or address"
                        />
                        <p className="ticket-detail__candidate-count" role="status">
                          Showing {visibleCandidates.length} of {filteredCandidates.length}{' '}
                          candidates
                        </p>
                      </div>

                      {selectedCandidates.length > 1 && (
                        <div className="ticket-detail__compare-selected">
                          <h5 className="ticket-detail__subsection-title">
                            Compare selected ({selectedCandidates.length})
                          </h5>
                          <ul className="ticket-detail__compare-selected-list">
                            {selectedCandidates.map((candidate) => (
                              <li key={candidate.ticketId}>
                                <strong>{candidate.ticketNumber}</strong>
                                <span>{formatCategory(candidate.category)}</span>
                                <span>{formatStatus(candidate.status)}</span>
                                <span>
                                  {candidate.distanceMeters !== undefined
                                    ? formatDistanceMeters(candidate.distanceMeters)
                                    : 'Distance unknown'}
                                </span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <ul className="ticket-detail__candidates">
                        {visibleCandidates.map((candidate) => {
                          const isExpanded = expandedDuplicateIds.includes(candidate.ticketId);
                          const comparison = comparisons[candidate.ticketId];
                          const panelId = `duplicate-comparison-${candidate.ticketId}`;
                          const canSelect = isCanonicalTicket && candidate.mergeable;

                          return (
                            <li key={candidate.ticketId} className="ticket-detail__candidate">
                              <div className="ticket-detail__candidate-row">
                                {canSelect && (
                                  <input
                                    type="checkbox"
                                    className="ticket-detail__candidate-checkbox"
                                    checked={selectedDuplicateIds.includes(candidate.ticketId)}
                                    onChange={() => toggleDuplicateSelection(candidate.ticketId)}
                                    disabled={isMerging}
                                    aria-label={`Select ${candidate.ticketNumber} as a duplicate`}
                                  />
                                )}

                                <CandidateThumb
                                  ticketNumber={candidate.ticketNumber}
                                  category={candidate.category}
                                  imageObjectKey={candidate.imageObjectKey}
                                  imageUrl={candidate.imageUrl}
                                />

                                <div className="ticket-detail__candidate-main">
                                  <div className="ticket-detail__candidate-heading">
                                    <Link
                                      to={`/tickets/${candidate.ticketId}`}
                                      className="ticket-detail__suggestion-link"
                                    >
                                      {candidate.ticketNumber}
                                    </Link>
                                    {candidate.suggested && (
                                      <span className="ticket-detail__match-hint">
                                        Suggested match
                                      </span>
                                    )}
                                    {!candidate.mergeable && (
                                      <span className="ticket-detail__match-hint">
                                        Not available to merge
                                      </span>
                                    )}
                                  </div>

                                  <p className="ticket-detail__candidate-excerpt">
                                    {describeExcerpt(candidate.description)}
                                  </p>

                                  <div className="ticket-detail__candidate-meta">
                                    <StatusBadge status={candidate.status} />
                                    <CategoryBadge category={candidate.category} />
                                    <PriorityBadge priority={candidate.priority} />
                                    {candidate.distanceMeters !== undefined && (
                                      <span>{formatDistanceMeters(candidate.distanceMeters)}</span>
                                    )}
                                    {candidate.createdAt && (
                                      <span>
                                        {formatTicketAge(candidate.createdAt)} old ·{' '}
                                        <time dateTime={candidate.createdAt}>
                                          {formatCreatedDate(candidate.createdAt)}
                                        </time>
                                      </span>
                                    )}
                                    <span>
                                      {candidate.addressText?.trim() || 'Location not provided'}
                                    </span>
                                  </div>
                                </div>

                                <button
                                  type="button"
                                  className="ticket-detail__ghost-button"
                                  aria-expanded={isExpanded}
                                  aria-controls={panelId}
                                  onClick={() => toggleCandidateExpanded(candidate.ticketId)}
                                >
                                  {isExpanded
                                    ? `Hide comparison for ${candidate.ticketNumber}`
                                    : `Compare ${candidate.ticketNumber}`}
                                </button>
                              </div>

                              {isExpanded && (
                                <div
                                  id={panelId}
                                  className="ticket-detail__comparison"
                                  role="region"
                                  aria-label={`Comparison of ${candidate.ticketNumber} with ${ticket.ticketNumber}`}
                                >
                                  {(!comparison || comparison.status === 'loading') && (
                                    <p className="ticket-detail__status-message" role="status">
                                      Loading comparison…
                                    </p>
                                  )}

                                  {comparison?.status === 'error' && (
                                    <div className="ticket-detail__comparison-error">
                                      <p className="ticket-detail__status-error" role="alert">
                                        {comparison.message}
                                      </p>
                                      <button
                                        type="button"
                                        className="ticket-detail__review-button ticket-detail__review-button--secondary"
                                        onClick={() => void loadComparison(candidate.ticketId)}
                                      >
                                        Retry comparison
                                      </button>
                                    </div>
                                  )}

                                  {comparison?.status === 'ready' && currentComparison && (
                                    <>
                                      <div className="ticket-detail__comparison-grid">
                                        <ComparisonColumn
                                          eyebrow="Current ticket"
                                          heading={currentComparison.ticketNumber}
                                          data={currentComparison}
                                        />
                                        <ComparisonColumn
                                          eyebrow="Duplicate candidate"
                                          heading={comparison.data.ticketNumber}
                                          data={comparison.data}
                                        />
                                      </div>
                                      <p className="ticket-detail__comparison-note">
                                        {(() => {
                                          const distance =
                                            candidate.distanceMeters ??
                                            distanceMetersBetween(
                                              currentComparison.location,
                                              comparison.data.location,
                                            ) ??
                                            null;
                                          return distance === null
                                            ? 'Distance between the two reports is unavailable.'
                                            : `Reported ${formatDistanceMeters(distance)} from the current ticket.`;
                                        })()}
                                      </p>
                                    </>
                                  )}
                                </div>
                              )}
                            </li>
                          );
                        })}
                      </ul>

                      {filteredCandidates.length > visibleCandidates.length && (
                        <p className="ticket-detail__merge-help">
                          Only the first {MAX_DUPLICATE_CANDIDATES} candidates are shown. Use the
                          filter to narrow the list.
                        </p>
                      )}
                    </>
                  )}

                  {isCanonicalTicket && effectiveCategory !== null && (
                    <div className="ticket-detail__merge-controls">
                      <p className="ticket-detail__merge-help">
                        {ticket.duplicateGroupId
                          ? 'Add more same-category tickets to this duplicate group.'
                          : 'Choose other same-category tickets to link under this main report.'}
                      </p>
                      <button
                        type="button"
                        className="ticket-detail__review-button"
                        onClick={() => setIsMergeDialogOpen(true)}
                        disabled={isMerging || selectedDuplicateIds.length === 0}
                      >
                        {isMerging ? 'Merging...' : 'Merge selected as duplicates'}
                      </button>
                      {mergeError && (
                        <p className="ticket-detail__status-error" role="alert">
                          {mergeError}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </section>
            )}

            {activeSection === 'activity' && (
              <section
                id={ticketDetailPanelId('activity')}
                role="tabpanel"
                tabIndex={0}
                aria-labelledby={ticketDetailTabId('activity')}
                className="ticket-detail__panel"
              >
                <h3 className="sr-only">Activity</h3>

                <div className="ticket-detail__card">
                  <h4 className="ticket-detail__card-title">Operational timeline</h4>
                  <p className="ticket-detail__card-hint">
                    Submission, status changes, and staff audit events, newest first.
                  </p>

                  {(ticket.statusHistory ?? []).length === 0 && (
                    <p className="ticket-detail__review-notice" role="status">
                      Status history is unavailable for this ticket; showing the activity that could
                      be loaded.
                    </p>
                  )}

                  {activityEvents.length === 0 ? (
                    <p className="ticket-detail__merge-empty">
                      No activity has been recorded for this ticket yet.
                    </p>
                  ) : (
                    <ol className="ticket-detail__activity" aria-label="Ticket activity timeline">
                      {activityEvents.map((event) => (
                        <li
                          key={event.id}
                          className={`ticket-detail__activity-item ticket-detail__activity-item--${event.kind}`}
                        >
                          <span className="ticket-detail__activity-marker" aria-hidden="true" />
                          <div className="ticket-detail__activity-body">
                            <div className="ticket-detail__activity-heading">
                              <span className="ticket-detail__activity-title">{event.title}</span>
                              <time
                                className="ticket-detail__activity-time"
                                dateTime={event.occurredAt}
                              >
                                {formatCreatedDate(event.occurredAt)}
                              </time>
                            </div>
                            {event.change && (
                              <p className="ticket-detail__activity-change">{event.change}</p>
                            )}
                            {event.detail && (
                              <p className="ticket-detail__activity-detail">{event.detail}</p>
                            )}
                            {event.actor && (
                              <p className="ticket-detail__activity-actor">By {event.actor}</p>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              </section>
            )}

            {isMergeDialogOpen && (
              <div
                className="ticket-detail__modal-backdrop"
                onKeyDown={(event) => {
                  if (event.key === 'Escape') {
                    setIsMergeDialogOpen(false);
                  }
                }}
              >
                <div
                  className="ticket-detail__modal"
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="merge-confirm-title"
                  aria-describedby="merge-confirm-description"
                >
                  <h4 id="merge-confirm-title" className="ticket-detail__modal-title">
                    Confirm duplicate merge
                  </h4>
                  <p id="merge-confirm-description" className="ticket-detail__modal-text">
                    {ticket.ticketNumber} stays the main (canonical) ticket. The selected reports
                    become duplicates linked to it. Their evidence and history stay preserved.
                  </p>
                  <ul className="ticket-detail__modal-list">
                    {selectedCandidates.map((candidate) => (
                      <li key={candidate.ticketId}>
                        {candidate.ticketNumber} becomes a duplicate of {ticket.ticketNumber}
                      </li>
                    ))}
                  </ul>
                  <div className="ticket-detail__modal-actions">
                    <button
                      type="button"
                      className="ticket-detail__ghost-button"
                      onClick={() => setIsMergeDialogOpen(false)}
                      disabled={isMerging}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      ref={confirmMergeRef}
                      className="ticket-detail__review-button ticket-detail__review-button--danger"
                      onClick={() => void handleMergeDuplicates()}
                      disabled={isMerging || selectedDuplicateIds.length === 0}
                    >
                      {isMerging ? 'Merging...' : 'Confirm merge'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, MouseEvent as ReactMouseEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import type {
  ActivityEvent as InternalActivityEvent,
  DuplicateCandidate,
  StaffComment,
  Ticket,
  TicketStatus,
} from '@/types/ticket';
import {
  assignTicketDepartment,
  assignTicketWorkforce,
  fetchDuplicateCandidates,
  fetchDuplicateComparison,
  createTicketComment,
  fetchTicketActivity,
  fetchTicketById,
  fetchTicketComments,
  mergeDuplicateTickets,
  reviewTicketCategory,
  updateTicketStatus,
} from '@/services/tickets';
import {
  assignWorkOrder,
  cancelWorkOrder,
  completeWorkOrder,
  createTicketWorkOrder,
  listTicketWorkOrders,
  startWorkOrder,
  uploadWorkOrderEvidence,
} from '@/services/workOrders';
import { fetchResolutionFeedback, reviewResolutionFeedback } from '@/services/resolutionFeedback';
import type { StaffResolutionFeedback } from '@/types/resolutionFeedback';
import { useI18n } from '@/i18n/LocaleProvider';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { EmptyState } from '@/components/EmptyState';
import { TicketPhoto } from '@/components/TicketPhoto';
import { ImagePrivacyStatus } from '@/components/ImagePrivacyStatus';
import { ImageRedactionReviewPanel } from '@/components/ImageRedactionReview';
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
import { listTeams, listWorkers } from '@/services/workforce';
import type { WorkOrder, WorkOrderEvidence } from '@/types/workOrder';

function workOrderAssigneeValue(order: WorkOrder | null | undefined): string {
  if (order?.assignedWorkerId) {
    return `worker:${order.assignedWorkerId}`;
  }
  if (order?.assignedTeamId) {
    return `team:${order.assignedTeamId}`;
  }
  return '';
}

function EvidencePhotoList({
  items,
  emptyLabel,
  category,
}: {
  items: WorkOrderEvidence[];
  emptyLabel: string;
  category: string;
}) {
  const { t } = useI18n();
  if (!items.length) {
    return <p className="ticket-detail__card-hint">{emptyLabel}</p>;
  }
  return (
    <div className="ticket-detail__evidence-list">
      {items.map((item) => (
        <TicketPhoto
          key={item.evidenceId}
          imageObjectKey={item.objectKey}
          imageUrl={item.photoUrl ?? undefined}
          category={category}
          alt={t('ticket.workOrder.evidenceAlt', {
            kind: item.kind.replaceAll('_', ' ').toLowerCase(),
          })}
        />
      ))}
    </div>
  );
}
import type { WorkforceTeam, WorkforceWorker } from '@/types/workforce';
import {
  formatWorkOrderState,
  reasonsForKind,
  requiredOutcomeKind,
  workOrderCancelReasons,
} from '@/utils/outcomeReasons';
import { IconImage, IconLocation, IconSparkles, IconWorkflow } from '@/components/icons';
import {
  parseTicketDetailSection,
  TICKET_DETAIL_SECTION_PARAM,
  ticketDetailSectionLabel,
  TICKET_DETAIL_SECTIONS,
  ticketDetailPanelId,
  ticketDetailTabId,
  type TicketDetailSection,
} from './ticketDetail/sections';
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

type CandidateLoadState = 'idle' | 'loading' | 'ready' | 'error';

/** Server-side search runs after typing settles so each keystroke is not a request. */
const CANDIDATE_SEARCH_DEBOUNCE_MS = 250;

function CandidateThumb({
  ticketNumber,
  category,
  imageUrl,
}: {
  ticketNumber: string;
  category: string;
  imageUrl?: string;
}) {
  const { t } = useI18n();
  // Candidates carry a presigned URL only; there is no raw storage key to resolve.
  const resolvedUrl = imageUrl ? getTicketImageUrl(undefined, category, imageUrl) : null;

  if (!resolvedUrl) {
    return (
      <span
        className="ticket-detail__thumb ticket-detail__thumb--empty"
        role="img"
        aria-label={t('ticket.noPhoto', { ticketNumber })}
      >
        <IconImage className="ticket-detail__thumb-icon" />
      </span>
    );
  }

  return (
    <img
      className="ticket-detail__thumb"
      src={resolvedUrl}
      alt={t('ticket.photoAlt', { ticketNumber })}
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
  const { t } = useI18n();
  return (
    <div className="ticket-detail__comparison-column">
      <p className="ticket-detail__eyebrow">{eyebrow}</p>
      <h5 className="ticket-detail__comparison-title">{heading}</h5>
      <TicketPhoto
        imageUrl={data.imageUrl}
        category={data.category}
        alt={t('ticket.photoAlt', { ticketNumber: data.ticketNumber })}
      />
      <p className="ticket-detail__comparison-description">{data.description}</p>
      <dl className="ticket-detail__comparison-facts">
        <div>
          <dt>{t('ticket.status')}</dt>
          <dd>
            <StatusBadge status={data.status} />
          </dd>
        </div>
        <div>
          <dt>{t('ticket.category')}</dt>
          <dd>
            <CategoryBadge category={data.category} />
          </dd>
        </div>
        <div>
          <dt>{t('ticket.priority')}</dt>
          <dd>
            <PriorityBadge priority={data.priority} />
          </dd>
        </div>
        <div>
          <dt>{t('ticket.submitted')}</dt>
          <dd>
            <time dateTime={data.createdAt}>{formatCreatedDate(data.createdAt)}</time>
          </dd>
        </div>
        <div>
          <dt>{t('ticket.location')}</dt>
          <dd>{data.location.addressText || t('ticket.noAddress')}</dd>
        </div>
      </dl>
    </div>
  );
}

type TicketDetailPageProps = {
  ticketId?: string;
  embedded?: boolean;
  onTicketUpdated?: (ticket: Ticket) => void;
};

export function TicketDetailPage({
  ticketId: ticketIdProp,
  embedded = false,
  onTicketUpdated,
}: TicketDetailPageProps = {}) {
  const { t } = useI18n();
  const { ticketId: routeTicketId } = useParams<{ ticketId: string }>();
  const navigate = useNavigate();
  const ticketId = ticketIdProp ?? routeTicketId;
  const { session } = useStaffAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [embeddedSection, setEmbeddedSection] = useState<TicketDetailSection>('review');
  const activeSection = embedded
    ? embeddedSection
    : parseTicketDetailSection(searchParams.get(TICKET_DETAIL_SECTION_PARAM));

  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [pendingStatus, setPendingStatus] = useState<TicketStatus | ''>('');
  const [statusUpdateError, setStatusUpdateError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categoryReviewError, setCategoryReviewError] = useState<string | null>(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState('');
  const [departmentUpdateError, setDepartmentUpdateError] = useState<string | null>(null);
  const [workers, setWorkers] = useState<WorkforceWorker[]>([]);
  const [teams, setTeams] = useState<WorkforceTeam[]>([]);
  const [selectedWorkforceValue, setSelectedWorkforceValue] = useState('');
  const [workforceError, setWorkforceError] = useState<string | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [activeWorkOrderId, setActiveWorkOrderId] = useState<string | null>(null);
  const [workOrderError, setWorkOrderError] = useState<string | null>(null);
  const [workOrderSuccess, setWorkOrderSuccess] = useState<string | null>(null);
  const [isMutatingWorkOrder, setIsMutatingWorkOrder] = useState(false);
  const [workOrderSummary, setWorkOrderSummary] = useState('');
  const [workOrderAssignee, setWorkOrderAssignee] = useState('');
  const [workOrderCancelReason, setWorkOrderCancelReason] = useState('');
  const [workOrderNote, setWorkOrderNote] = useState('');
  const [isUploadingEvidence, setIsUploadingEvidence] = useState(false);
  const [resolutionFeedback, setResolutionFeedback] = useState<StaffResolutionFeedback | null>(
    null,
  );
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [isReviewingFeedback, setIsReviewingFeedback] = useState(false);
  const [statusReasonCode, setStatusReasonCode] = useState('');
  const [statusPrivateNote, setStatusPrivateNote] = useState('');
  const [isSavingChanges, setIsSavingChanges] = useState(false);
  const [saveChangesError, setSaveChangesError] = useState<string | null>(null);
  const [pendingLeaveAction, setPendingLeaveAction] = useState<(() => void) | null>(null);

  const persistedWorkforceValue = ticket?.assignedWorkerId
    ? `worker:${ticket.assignedWorkerId}`
    : ticket?.assignedTeamId
      ? `team:${ticket.assignedTeamId}`
      : '';
  const statusDirty = Boolean(ticket && pendingStatus && pendingStatus !== ticket.status);
  const departmentDirty = Boolean(ticket && selectedDepartmentId !== (ticket.departmentId ?? ''));
  const workforceDirty = Boolean(ticket && selectedWorkforceValue !== persistedWorkforceValue);
  const categoryDirty = Boolean(ticket && selectedCategory !== (ticket.ai?.finalCategory ?? ''));
  const unsavedChangeCount = [statusDirty, departmentDirty, workforceDirty, categoryDirty].filter(
    Boolean,
  ).length;
  const hasUnsavedChanges = unsavedChangeCount > 0;

  const [duplicateCandidates, setDuplicateCandidates] = useState<DuplicateCandidate[]>([]);
  const [candidateLoadState, setCandidateLoadState] = useState<CandidateLoadState>('idle');
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const [candidateNextCursor, setCandidateNextCursor] = useState<string | null>(null);
  const [isLoadingMoreCandidates, setIsLoadingMoreCandidates] = useState(false);
  const [selectedDuplicateIds, setSelectedDuplicateIds] = useState<string[]>([]);
  /** Keeps selected rows describable even after a search narrows the visible page. */
  const [selectedCandidatesById, setSelectedCandidatesById] = useState<
    Record<string, DuplicateCandidate>
  >({});
  const [expandedDuplicateIds, setExpandedDuplicateIds] = useState<string[]>([]);
  const [comparisons, setComparisons] = useState<Record<string, ComparisonState>>({});
  const [candidateFilter, setCandidateFilter] = useState('');
  const [candidateQuery, setCandidateQuery] = useState('');
  const [isMergeDialogOpen, setIsMergeDialogOpen] = useState(false);
  const [mergeError, setMergeError] = useState<string | null>(null);
  const [isMerging, setIsMerging] = useState(false);

  const [internalActivity, setInternalActivity] = useState<InternalActivityEvent[]>([]);
  const [comments, setComments] = useState<StaffComment[]>([]);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [nextActivityCursor, setNextActivityCursor] = useState<string | null>(null);
  const [isLoadingMoreActivity, setIsLoadingMoreActivity] = useState(false);
  const [loadMoreActivityError, setLoadMoreActivityError] = useState<string | null>(null);
  const [activityRefreshKey, setActivityRefreshKey] = useState(0);
  const [commentsRefreshKey, setCommentsRefreshKey] = useState(0);
  const [commentText, setCommentText] = useState('');
  const [commentError, setCommentError] = useState<string | null>(null);
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  const loadedTicketRef = useRef<Ticket | null>(null);
  const currentTicketId = useRef<string | undefined>(ticketId);
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
        setSelectedCategory(data.ai?.finalCategory ?? '');
        setSelectedDepartmentId(data.departmentId ?? '');
        setSelectedWorkforceValue(
          data.assignedWorkerId
            ? `worker:${data.assignedWorkerId}`
            : data.assignedTeamId
              ? `team:${data.assignedTeamId}`
              : '',
        );
        setStatusReasonCode('');
        setStatusPrivateNote('');
        try {
          const listed = await listTicketWorkOrders(requestedTicketId);
          if (!cancelled) {
            setWorkOrders(listed.items);
            setActiveWorkOrderId(listed.activeWorkOrderId);
            const active =
              listed.items.find((item) => item.workOrderId === listed.activeWorkOrderId) ?? null;
            setWorkOrderAssignee(workOrderAssigneeValue(active));
            setWorkOrderSummary('');
            setWorkOrderCancelReason('');
            setWorkOrderError(null);
          }
        } catch (error) {
          if (!cancelled) {
            setWorkOrders([]);
            setActiveWorkOrderId(data.activeWorkOrderId ?? null);
            setWorkOrderAssignee(
              data.assignedWorkerId
                ? `worker:${data.assignedWorkerId}`
                : data.assignedTeamId
                  ? `team:${data.assignedTeamId}`
                  : '',
            );
            setWorkOrderError(
              error instanceof Error ? error.message : t('ticket.workOrder.unableLoad'),
            );
          }
        }
        try {
          const feedback = await fetchResolutionFeedback(requestedTicketId);
          if (!cancelled) {
            setResolutionFeedback(feedback);
            setFeedbackError(null);
          }
        } catch {
          if (!cancelled) {
            setResolutionFeedback(null);
          }
        }
        setDepartmentUpdateError(null);
        setSelectedDuplicateIds([]);
        setSelectedCandidatesById({});
        setMergeError(null);
        setLoadState('success');
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : t('errors.loadTicket'));
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

  useEffect(() => {
    currentTicketId.current = ticketId;
    setInternalActivity([]);
    setComments([]);
    setNextActivityCursor(null);
    setLoadMoreActivityError(null);
    setCommentText('');
    setCommentError(null);
    setIsSubmittingComment(false);
    if (embedded) {
      setEmbeddedSection('review');
    }
  }, [embedded, ticketId]);

  const notifiedTicketRef = useRef<string | null>(null);
  useEffect(() => {
    if (!ticket || loadState !== 'success' || !onTicketUpdated) {
      return;
    }
    const signature = [
      ticket.ticketId,
      ticket.updatedAt,
      ticket.status,
      ticket.departmentId ?? '',
      ticket.category,
    ].join(':');
    if (notifiedTicketRef.current === signature) {
      return;
    }
    notifiedTicketRef.current = signature;
    onTicketUpdated(ticket);
  }, [loadState, onTicketUpdated, ticket]);

  useEffect(() => {
    let cancelled = false;
    async function loadDirectory() {
      try {
        const municipalityId = ticket?.municipalityId ?? session?.municipalityId ?? undefined;
        const [nextWorkers, nextTeams] = await Promise.all([
          listWorkers(municipalityId),
          listTeams(municipalityId),
        ]);
        if (!cancelled) {
          setWorkers(nextWorkers);
          setTeams(nextTeams);
        }
      } catch {
        if (!cancelled) {
          setWorkers([]);
          setTeams([]);
        }
      }
    }
    void loadDirectory();
    return () => {
      cancelled = true;
    };
  }, [ticketId, ticket?.municipalityId, session?.municipalityId]);

  useEffect(() => {
    if (!ticketId) return;
    let active = true;
    setActivityLoading(true);
    setActivityError(null);
    setLoadMoreActivityError(null);
    void fetchTicketActivity(ticketId)
      .then((page) => {
        if (!active) return;
        setInternalActivity(page.events);
        setNextActivityCursor(page.nextCursor);
      })
      .catch((error) => {
        if (active) {
          setActivityError(
            error instanceof Error ? error.message : t('ticket.activity.unableLoad'),
          );
        }
      })
      .finally(() => {
        if (active) setActivityLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activityRefreshKey, ticketId]);

  useEffect(() => {
    if (!ticketId) return;
    let active = true;
    setCommentsLoading(true);
    setCommentsError(null);
    void fetchTicketComments(ticketId)
      .then((loadedComments) => {
        if (active) setComments(loadedComments);
      })
      .catch((error) => {
        if (active) {
          setCommentsError(
            error instanceof Error ? error.message : t('ticket.comments.unableLoad'),
          );
        }
      })
      .finally(() => {
        if (active) setCommentsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [commentsRefreshKey, ticketId]);

  async function loadMoreActivity() {
    if (!ticketId || !nextActivityCursor || isLoadingMoreActivity) return;
    const requestedTicketId = ticketId;
    const requestedCursor = nextActivityCursor;
    setIsLoadingMoreActivity(true);
    setLoadMoreActivityError(null);
    try {
      const page = await fetchTicketActivity(requestedTicketId, requestedCursor);
      if (currentTicketId.current !== requestedTicketId) return;
      setInternalActivity((current) => {
        const ids = new Set(current.map((event) => event.eventId));
        return [...current, ...page.events.filter((event) => !ids.has(event.eventId))];
      });
      setNextActivityCursor(page.nextCursor);
    } catch (error) {
      if (currentTicketId.current === requestedTicketId) {
        setLoadMoreActivityError(
          error instanceof Error ? error.message : t('ticket.activity.unableLoadMore'),
        );
      }
    } finally {
      if (currentTicketId.current === requestedTicketId) setIsLoadingMoreActivity(false);
    }
  }

  async function handleCommentSubmit() {
    if (!ticketId || !commentText.trim()) return;
    const requestedTicketId = ticketId;
    const requestedCommentText = commentText;
    setIsSubmittingComment(true);
    setCommentError(null);
    let comment: StaffComment;
    try {
      comment = await createTicketComment(requestedTicketId, requestedCommentText);
    } catch (error) {
      if (currentTicketId.current !== requestedTicketId) return;
      setCommentError(error instanceof Error ? error.message : t('ticket.comments.unableAdd'));
      setIsSubmittingComment(false);
      return;
    }
    if (currentTicketId.current !== requestedTicketId) return;
    setCommentText('');
    setComments((current) =>
      current.some((item) => item.commentId === comment.commentId)
        ? current
        : [...current, comment],
    );
    try {
      const page = await fetchTicketActivity(requestedTicketId);
      if (currentTicketId.current !== requestedTicketId) return;
      setInternalActivity(page.events);
      setNextActivityCursor(page.nextCursor);
      setActivityError(null);
    } catch (error) {
      if (currentTicketId.current === requestedTicketId) {
        setActivityError(
          error instanceof Error ? error.message : t('ticket.activity.unableRefresh'),
        );
      }
    } finally {
      if (currentTicketId.current === requestedTicketId) setIsSubmittingComment(false);
    }
  }

  useEffect(() => {
    if (!hasUnsavedChanges) {
      return;
    }
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [hasUnsavedChanges]);

  const handleSaveChanges = async (): Promise<boolean> => {
    if (!ticket || !hasUnsavedChanges) {
      return true;
    }

    const outcomeKind = pendingStatus ? requiredOutcomeKind(ticket.status, pendingStatus) : null;
    if (statusDirty && outcomeKind && !statusReasonCode) {
      setStatusUpdateError(t('ticket.review.selectReasonBeforeStatus'));
      return false;
    }
    if (departmentDirty && !isKnownDepartmentId(selectedDepartmentId)) {
      setDepartmentUpdateError(t('ticket.review.selectDepartmentBeforeSave'));
      return false;
    }
    if (
      categoryDirty &&
      !SUPPORTED_CATEGORY_OPTIONS.some((category) => category === selectedCategory)
    ) {
      setCategoryReviewError(t('ticket.review.selectCategoryBeforeSave'));
      return false;
    }

    setIsSavingChanges(true);
    setSaveChangesError(null);
    setStatusUpdateError(null);
    setDepartmentUpdateError(null);
    setWorkforceError(null);
    setCategoryReviewError(null);

    try {
      let updatedTicket: Ticket | null = ticket;
      if (statusDirty && pendingStatus) {
        updatedTicket = await updateTicketStatus(ticket.ticketId, pendingStatus, {
          reasonCode: outcomeKind ? statusReasonCode : undefined,
          note: statusPrivateNote.trim() || undefined,
        });
      }
      if (updatedTicket && departmentDirty) {
        updatedTicket = await assignTicketDepartment(ticket.ticketId, {
          departmentId: selectedDepartmentId,
          updatedBy: session?.username,
        });
      }
      if (updatedTicket && workforceDirty) {
        const payload =
          selectedWorkforceValue === ''
            ? { clear: true }
            : selectedWorkforceValue.startsWith('team:')
              ? { teamId: selectedWorkforceValue.slice('team:'.length) }
              : { workerId: selectedWorkforceValue.slice('worker:'.length) };
        updatedTicket = await assignTicketWorkforce(ticket.ticketId, payload);
      }
      if (updatedTicket && categoryDirty) {
        updatedTicket = await reviewTicketCategory(ticket.ticketId, {
          finalCategory: selectedCategory,
        });
      }
      if (!updatedTicket) {
        loadedTicketRef.current = null;
        setTicket(null);
        setLoadState('not-found');
        return false;
      }

      loadedTicketRef.current = updatedTicket;
      setTicket(updatedTicket);
      setPendingStatus(updatedTicket.status);
      setSelectedDepartmentId(updatedTicket.departmentId ?? '');
      setSelectedWorkforceValue(
        updatedTicket.assignedWorkerId
          ? `worker:${updatedTicket.assignedWorkerId}`
          : updatedTicket.assignedTeamId
            ? `team:${updatedTicket.assignedTeamId}`
            : '',
      );
      setSelectedCategory(updatedTicket.ai?.finalCategory ?? '');
      setStatusReasonCode('');
      setStatusPrivateNote('');
      return true;
    } catch (error) {
      setSaveChangesError(
        error instanceof Error ? error.message : t('ticket.review.unableSaveChanges'),
      );
      return false;
    } finally {
      setIsSavingChanges(false);
    }
  };

  const requestLeave = useCallback(
    (action: () => void) => {
      if (!hasUnsavedChanges) {
        action();
        return;
      }
      setPendingLeaveAction(() => action);
    },
    [hasUnsavedChanges],
  );

  const selectSection = useCallback(
    (section: TicketDetailSection) => {
      requestLeave(() => {
        if (embedded) {
          setEmbeddedSection(section);
          return;
        }
        setSearchParams(
          (current) => {
            const next = new URLSearchParams(current);
            next.set(TICKET_DETAIL_SECTION_PARAM, section);
            return next;
          },
          { replace: false },
        );
      });
    },
    [embedded, requestLeave, setSearchParams],
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
    requestLeave(() => setRefreshToken((current) => current + 1));
  };

  const handleWorkspaceClickCapture = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!hasUnsavedChanges || event.defaultPrevented || event.button !== 0) {
      return;
    }
    const target = event.target as HTMLElement;
    const anchor = target.closest('a[href]') as HTMLAnchorElement | null;
    if (!anchor || anchor.target === '_blank' || event.metaKey || event.ctrlKey || event.shiftKey) {
      return;
    }
    const href = anchor.getAttribute('href');
    if (!href || !href.startsWith('/')) {
      return;
    }
    event.preventDefault();
    requestLeave(() => navigate(href));
  };

  const discardPendingChanges = () => {
    if (!ticket) {
      return;
    }
    setPendingStatus(ticket.status);
    setSelectedDepartmentId(ticket.departmentId ?? '');
    setSelectedWorkforceValue(persistedWorkforceValue);
    setSelectedCategory(ticket.ai?.finalCategory ?? '');
    setStatusReasonCode('');
    setStatusPrivateNote('');
    setSaveChangesError(null);
  };

  const refreshWorkOrders = async (ticketIdToLoad: string) => {
    const listed = await listTicketWorkOrders(ticketIdToLoad);
    setWorkOrders(listed.items);
    setActiveWorkOrderId(listed.activeWorkOrderId);
    const active =
      listed.items.find((item) => item.workOrderId === listed.activeWorkOrderId) ?? null;
    setWorkOrderAssignee(workOrderAssigneeValue(active));
    return listed;
  };

  const applyWorkOrderResult = async (workOrder: WorkOrder) => {
    if (!ticket) {
      return;
    }
    const updatedTicket = await fetchTicketById(ticket.ticketId);
    if (updatedTicket) {
      loadedTicketRef.current = updatedTicket;
      setTicket(updatedTicket);
      setPendingStatus(updatedTicket.status);
      setSelectedWorkforceValue(
        updatedTicket.assignedWorkerId
          ? `worker:${updatedTicket.assignedWorkerId}`
          : updatedTicket.assignedTeamId
            ? `team:${updatedTicket.assignedTeamId}`
            : '',
      );
    }
    await refreshWorkOrders(workOrder.ticketId);
  };

  const runWorkOrderMutation = async (action: () => Promise<WorkOrder>, success: string) => {
    setIsMutatingWorkOrder(true);
    setWorkOrderError(null);
    setWorkOrderSuccess(null);
    try {
      const result = await action();
      await applyWorkOrderResult(result);
      setWorkOrderSuccess(success);
      setWorkOrderNote('');
    } catch (error) {
      setWorkOrderError(
        error instanceof Error ? error.message : t('ticket.workOrder.unableUpdate'),
      );
    } finally {
      setIsMutatingWorkOrder(false);
    }
  };

  const handleCreateWorkOrder = async () => {
    if (!ticket) {
      return;
    }
    const assignee =
      workOrderAssignee === ''
        ? {}
        : workOrderAssignee.startsWith('team:')
          ? { teamId: workOrderAssignee.slice('team:'.length) }
          : { workerId: workOrderAssignee.slice('worker:'.length) };
    await runWorkOrderMutation(
      () =>
        createTicketWorkOrder(ticket.ticketId, {
          summary: workOrderSummary.trim() || undefined,
          ...assignee,
        }),
      t('ticket.workOrder.saved'),
    );
  };

  const handleEvidenceUpload = async (
    workOrderId: string,
    kind: 'BEFORE' | 'AFTER',
    file: File | undefined,
  ) => {
    if (!file) {
      return;
    }
    setIsUploadingEvidence(true);
    setWorkOrderError(null);
    setWorkOrderSuccess(null);
    try {
      await uploadWorkOrderEvidence(workOrderId, kind, file);
      await refreshWorkOrders(ticket?.ticketId ?? '');
      setWorkOrderSuccess(
        kind === 'AFTER'
          ? t('ticket.workOrder.afterAttached')
          : t('ticket.workOrder.beforeAttached'),
      );
    } catch (error) {
      setWorkOrderError(
        error instanceof Error ? error.message : t('ticket.workOrder.unableUpload'),
      );
    } finally {
      setIsUploadingEvidence(false);
    }
  };

  const handleFeedbackReview = async (action: 'KEEP_RESOLVED' | 'RETURN_IN_PROGRESS') => {
    if (!ticket) {
      return;
    }
    setIsReviewingFeedback(true);
    setFeedbackError(null);
    try {
      const updated = await reviewResolutionFeedback(ticket.ticketId, action);
      setResolutionFeedback(updated);
      const refreshed = await fetchTicketById(ticket.ticketId);
      if (refreshed) {
        loadedTicketRef.current = refreshed;
        setTicket(refreshed);
        setPendingStatus(refreshed.status);
      }
    } catch (error) {
      setFeedbackError(error instanceof Error ? error.message : t('ticket.feedback.unableReview'));
    } finally {
      setIsReviewingFeedback(false);
    }
  };

  const activeWorkOrder = workOrders.find((item) => item.workOrderId === activeWorkOrderId) ?? null;
  const evidenceForDisplay = (activeWorkOrder?.evidence ?? []).concat(
    workOrders
      .flatMap((item) => item.evidence ?? [])
      .filter((item) => {
        if (!activeWorkOrder) {
          return true;
        }
        return item.workOrderId !== activeWorkOrder.workOrderId;
      }),
  );
  const citizenOriginalEvidence = evidenceForDisplay.filter(
    (item) => item.kind === 'ORIGINAL_REPORT',
  );
  const beforeEvidence = (activeWorkOrder?.evidence ?? []).filter((item) => item.kind === 'BEFORE');
  const afterEvidence = (activeWorkOrder?.evidence ?? []).filter((item) => item.kind === 'AFTER');
  const canCompleteWorkOrder =
    activeWorkOrder?.state === 'IN_PROGRESS' &&
    (activeWorkOrder.afterImageCount ?? afterEvidence.length) > 0;
  const pendingOutcomeKind =
    ticket && pendingStatus && pendingStatus !== ticket.status
      ? requiredOutcomeKind(ticket.status, pendingStatus)
      : null;

  const loadComparison = useCallback(async (candidateId: string) => {
    const sourceTicketId = loadedTicketRef.current?.ticketId;
    if (!sourceTicketId) {
      return;
    }

    requestedComparisonsRef.current.add(candidateId);
    setComparisons((current) => ({ ...current, [candidateId]: { status: 'loading' } }));

    try {
      // Bounded projection: no contact, tracking code, storage key, or history.
      const comparison = await fetchDuplicateComparison(sourceTicketId, candidateId);
      if (!comparison) {
        requestedComparisonsRef.current.delete(candidateId);
        setComparisons((current) => ({
          ...current,
          [candidateId]: {
            status: 'error',
            message: t('ticket.duplicates.candidateGone'),
          },
        }));
        return;
      }

      setComparisons((current) => ({
        ...current,
        [candidateId]: { status: 'ready', data: comparison },
      }));
    } catch (error) {
      // Allow a retry for this candidate only; other rows stay untouched.
      requestedComparisonsRef.current.delete(candidateId);
      setComparisons((current) => ({
        ...current,
        [candidateId]: {
          status: 'error',
          message:
            error instanceof Error ? error.message : t('ticket.duplicates.unableLoadComparison'),
        },
      }));
    }
  }, []);

  const ensureComparisonRequested = useCallback(
    (candidateId: string) => {
      if (!requestedComparisonsRef.current.has(candidateId)) {
        void loadComparison(candidateId);
      }
    },
    [loadComparison],
  );

  const toggleDuplicateSelection = (candidate: DuplicateCandidate) => {
    const isSelected = selectedDuplicateIds.includes(candidate.ticketId);
    setSelectedDuplicateIds((current) =>
      isSelected
        ? current.filter((id) => id !== candidate.ticketId)
        : [...current, candidate.ticketId],
    );
    setSelectedCandidatesById((current) => ({ ...current, [candidate.ticketId]: candidate }));
    setMergeError(null);

    if (!isSelected) {
      // Merging is only allowed once staff can see the comparison, so start it now.
      ensureComparisonRequested(candidate.ticketId);
    }
  };

  const toggleCandidateExpanded = (candidateId: string) => {
    setExpandedDuplicateIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );

    ensureComparisonRequested(candidateId);
  };

  const handleMergeDuplicates = async () => {
    if (!ticket) {
      return;
    }

    if (selectedDuplicateIds.length === 0) {
      setMergeError(t('ticket.duplicates.selectAtLeastOne'));
      return;
    }

    if (selectedDuplicateIds.some((id) => comparisons[id]?.status !== 'ready')) {
      setMergeError(t('ticket.duplicates.reviewBeforeMerge'));
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
        setMergeError(t('ticket.duplicates.notFound'));
        return;
      }

      loadedTicketRef.current = updatedTicket;
      setTicket(updatedTicket);
      setDuplicateCandidates((current) =>
        current.filter((candidate) => !selectedDuplicateIds.includes(candidate.ticketId)),
      );
      setExpandedDuplicateIds((current) =>
        current.filter((id) => !selectedDuplicateIds.includes(id)),
      );
      setSelectedDuplicateIds([]);
      setSelectedCandidatesById({});
      setIsMergeDialogOpen(false);
    } catch (error) {
      const message = error instanceof Error ? error.message : t('ticket.duplicates.unableMerge');
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

  const unifiedInternalActivity = useMemo(() => {
    const commentsById = new Map(comments.map((comment) => [comment.commentId, comment]));
    const linkedCommentIds = new Set<string>();
    const items = internalActivity.map((event) => {
      const commentId = event.eventType === 'STAFF_COMMENT' ? event.details.commentId : undefined;
      const comment = commentId ? commentsById.get(commentId) : undefined;
      if (commentId) linkedCommentIds.add(commentId);
      return { event, comment };
    });

    // Keep comments available when activity fails, and show a new comment while
    // its follow-up activity refresh is still pending.
    for (const comment of comments) {
      if (linkedCommentIds.has(comment.commentId)) continue;
      items.push({
        event: {
          eventId: `comment:${comment.commentId}`,
          eventType: 'STAFF_COMMENT',
          occurredAt: comment.createdAt,
          actorDisplayName: comment.authorDisplayName,
          details: { commentId: comment.commentId },
          sourceReference: `comment:${comment.commentId}`,
        },
        comment,
      });
    }

    return items.sort((left, right) => {
      const timestampDelta = Date.parse(left.event.occurredAt) - Date.parse(right.event.occurredAt);
      return timestampDelta || left.event.eventId.localeCompare(right.event.eventId);
    });
  }, [comments, internalActivity]);

  const suggestionCount = ticket?.duplicateSuggestions?.length ?? 0;
  const effectiveCategory = ticket ? effectiveTicketCategory(ticket) : null;
  const isCanonicalTicket =
    !!ticket &&
    (!ticket.duplicateGroupId || ticket.duplicateGroup?.canonicalTicketId === ticket.ticketId);

  useEffect(() => {
    const timer = setTimeout(
      () => setCandidateQuery(candidateFilter.trim()),
      CANDIDATE_SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [candidateFilter]);

  // The candidate source is only known once the ticket resolves with a usable
  // (reviewed or AI-suggested) category; unclassified tickets match everything.
  const candidateSourceId = loadState === 'success' && effectiveCategory !== null ? ticketId : null;

  useEffect(() => {
    if (!candidateSourceId) {
      setDuplicateCandidates([]);
      setCandidateNextCursor(null);
      setCandidateError(null);
      setCandidateLoadState('idle');
      return;
    }

    const controller = new AbortController();
    setCandidateLoadState('loading');
    setCandidateError(null);

    async function loadCandidates(sourceTicketId: string) {
      try {
        const page = await fetchDuplicateCandidates(sourceTicketId, {
          q: candidateQuery || undefined,
          signal: controller.signal,
        });
        if (controller.signal.aborted) {
          return;
        }
        setDuplicateCandidates(page.items);
        setCandidateNextCursor(page.nextCursor);
        setCandidateLoadState('ready');
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setDuplicateCandidates([]);
        setCandidateNextCursor(null);
        setCandidateError(
          error instanceof Error ? error.message : t('ticket.duplicates.unableLoad'),
        );
        setCandidateLoadState('error');
      }
    }

    void loadCandidates(candidateSourceId);

    return () => controller.abort();
  }, [candidateSourceId, candidateQuery, refreshToken]);

  const handleLoadMoreCandidates = async () => {
    if (!candidateSourceId || !candidateNextCursor || isLoadingMoreCandidates) {
      return;
    }

    setIsLoadingMoreCandidates(true);
    setCandidateError(null);

    try {
      const page = await fetchDuplicateCandidates(candidateSourceId, {
        q: candidateQuery || undefined,
        cursor: candidateNextCursor,
      });
      setDuplicateCandidates((current) => {
        const seen = new Set(current.map((candidate) => candidate.ticketId));
        return [...current, ...page.items.filter((item) => !seen.has(item.ticketId))];
      });
      setCandidateNextCursor(page.nextCursor);
    } catch (error) {
      setCandidateError(
        error instanceof Error ? error.message : t('ticket.duplicates.unableLoadMore'),
      );
    } finally {
      setIsLoadingMoreCandidates(false);
    }
  };

  const selectedCandidates = selectedDuplicateIds.flatMap((candidateId) => {
    const candidate =
      duplicateCandidates.find((item) => item.ticketId === candidateId) ??
      selectedCandidatesById[candidateId];
    return candidate ? [candidate] : [];
  });
  const unresolvedSelectionCount = selectedDuplicateIds.filter(
    (candidateId) => comparisons[candidateId]?.status !== 'ready',
  ).length;
  const failedSelectionCount = selectedDuplicateIds.filter(
    (candidateId) => comparisons[candidateId]?.status === 'error',
  ).length;
  /** Merging is a destructive link, so every selected report must be reviewable. */
  const canMergeSelection = selectedDuplicateIds.length > 0 && unresolvedSelectionCount === 0;

  const workspace = (
    <div
      className={`ticket-detail-page${embedded ? ' ticket-detail-page--embedded' : ''}`}
      onClickCapture={handleWorkspaceClickCapture}
    >
      {!embedded && (
        <Link to="/" className="ticket-detail-page__back">
          {t('ticket.back')}
        </Link>
      )}

      {loadState === 'loading' && <LoadingState message={t('ticket.loading')} />}

      {loadState === 'error' && (
        <div className="ticket-detail-page__error" role="alert">
          <h3>{t('ticket.unableLoad')}</h3>
          <p>{errorMessage}</p>
        </div>
      )}

      {loadState === 'not-found' && (
        <EmptyState title={t('ticket.notFoundTitle')} message={t('ticket.notFoundBody')} />
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
                  {ticket.ai?.urgencyScore !== undefined && (
                    <span className="ticket-detail__summary-urgency">
                      <strong>{t('ticket.review.urgencyTitle')}</strong>
                      {formatUrgencySummary(ticket.ai.urgencyScore)}
                      <span
                        className="ticket-detail__ai-icon"
                        aria-label={t('ticket.review.aiAssisted')}
                      >
                        <IconSparkles />
                      </span>
                      {ticket.ai.urgencyReason && (
                        <span
                          className="ticket-detail__compact-info"
                          tabIndex={0}
                          aria-label={t('ticket.review.whyScore')}
                        >
                          ⓘ<span role="tooltip">{ticket.ai.urgencyReason}</span>
                        </span>
                      )}
                    </span>
                  )}
                </div>
              </div>

              <div className="ticket-detail__summary-actions">
                <button
                  type="button"
                  className="ticket-detail__primary-action"
                  onClick={() => selectSection('review')}
                >
                  {t('ticket.reviewUpdate')}
                </button>
                <button
                  type="button"
                  className="ticket-detail__ghost-button"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? t('ticket.refreshing') : t('ticket.refresh')}
                </button>
              </div>
            </div>

            <dl className="ticket-detail__summary-meta">
              <div className="ticket-detail__summary-meta-item">
                <dt>{t('ticket.age')}</dt>
                <dd>{t('ticket.ageValue', { age: formatTicketAge(ticket.createdAt) })}</dd>
              </div>
              <div className="ticket-detail__summary-meta-item">
                <dt>{t('ticket.department')}</dt>
                <dd>{ticket.departmentName ?? formatDepartment(ticket.departmentId)}</dd>
              </div>
              <div className="ticket-detail__summary-meta-item">
                <dt>{t('ticket.category')}</dt>
                <dd>
                  {effectiveCategory
                    ? formatCategory(effectiveCategory)
                    : t('ticket.pendingCategory')}
                </dd>
              </div>
              {ticket.sla && ticket.sla.state !== 'unavailable' && (
                <div className="ticket-detail__summary-meta-item">
                  <dt>{t('ticket.sla')}</dt>
                  <dd>{ticket.sla.state.replace(/_/g, ' ')}</dd>
                </div>
              )}
            </dl>

            {isRefreshing && (
              <p className="ticket-detail__refresh-status" role="status">
                {t('ticket.refreshingTicket')}
              </p>
            )}
            {!isRefreshing && errorMessage && (
              <p className="ticket-detail__status-error" role="alert">
                {errorMessage}
              </p>
            )}

            <details className="ticket-detail__technical">
              <summary>{t('ticket.technical')}</summary>
              <dl className="ticket-detail__technical-list">
                <div>
                  <dt>{t('ticket.trackingCode')}</dt>
                  <dd className="ticket-detail__mono">{ticket.trackingCode}</dd>
                </div>
                <div>
                  <dt>{t('ticket.internalId')}</dt>
                  <dd className="ticket-detail__mono">{ticket.ticketId}</dd>
                </div>
                <div>
                  <dt>{t('ticket.evidenceKey')}</dt>
                  <dd className="ticket-detail__mono">{ticket.imageObjectKey}</dd>
                </div>
                <div>
                  <dt>{t('ticket.created')}</dt>
                  <dd>
                    <time dateTime={ticket.createdAt}>{formatCreatedDate(ticket.createdAt)}</time>
                  </dd>
                </div>
                {ticket.updatedAt && (
                  <div>
                    <dt>{t('ticket.lastUpdated')}</dt>
                    <dd>
                      <time dateTime={ticket.updatedAt}>{formatCreatedDate(ticket.updatedAt)}</time>
                    </dd>
                  </div>
                )}
              </dl>
            </details>
          </header>

          <div className="ticket-detail__tabs" role="tablist" aria-label={t('ticket.sectionsA11y')}>
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
                      ? t('ticket.duplicatesA11y', { count: suggestionCount })
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
                  {ticketDetailSectionLabel(section)}
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
              <h3 className="sr-only">{t('ticket.section.overview')}</h3>

              <div className="ticket-detail__next-action">
                <span className="ticket-detail__next-action-icon" aria-hidden="true">
                  <IconWorkflow />
                </span>
                <div>
                  <p className="ticket-detail__next-action-title">{t('ticket.nextAction')}</p>
                  <p className="ticket-detail__next-action-text">
                    {getStaffNextAction(ticket.status)}
                  </p>
                </div>
              </div>

              <div className="ticket-detail__overview-grid">
                <div className="ticket-detail__card">
                  <h4 className="ticket-detail__card-title">{t('ticket.citizenReport')}</h4>
                  <p className="ticket-detail__description">{ticket.description}</p>
                  <div className="ticket-detail__overview-photo">
                    <TicketPhoto
                      imageObjectKey={ticket.imageObjectKey}
                      imageUrl={ticket.imageUrl}
                      category={effectiveCategory ?? ticket.category}
                      alt={t('ticket.photoAlt', { ticketNumber: ticket.ticketNumber })}
                    />
                    <ImagePrivacyStatus redaction={ticket.imageRedaction} />
                  </div>
                </div>

                <div className="ticket-detail__card">
                  <h4 className="ticket-detail__card-title">
                    <span className="ticket-detail__card-title-icon" aria-hidden="true">
                      <IconLocation />
                    </span>
                    {t('ticket.location')}
                  </h4>
                  <p className="ticket-detail__location-text">
                    {ticket.location.addressText.trim() || t('ticket.noAddress')}
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
                        {t('ticket.openMaps')}
                      </a>
                      <TicketMap tickets={[ticket]} variant="detail" />
                    </>
                  ) : (
                    <p className="ticket-detail__location-unavailable">
                      {t('ticket.noCoordinates')}
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
              className="ticket-detail__panel ticket-detail__panel--review"
            >
              <h3 className="sr-only">{t('ticket.review.heading')}</h3>

              <p className="ticket-detail__ai-disclaimer">
                <span className="ticket-detail__ai-icon" aria-hidden="true">
                  <IconSparkles />
                </span>
                {t('ticket.review.aiWarning')}
              </p>

              <div className="ticket-detail__review-controls">
                <div className="ticket-detail__card ticket-detail__card--municipal">
                  <h4 className="ticket-detail__card-title">{t('ticket.review.municipalTitle')}</h4>
                  <p className="ticket-detail__card-hint">{t('ticket.review.municipalHint')}</p>

                  <div className="ticket-detail__actions-grid">
                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__eyebrow">{t('ticket.review.statusEyebrow')}</p>
                      <p className="ticket-detail__current-value">
                        {t('ticket.review.currentPrefix')} <StatusBadge status={ticket.status} />
                      </p>
                      <div className="ticket-detail__control-row">
                        <label htmlFor="status-update-select">
                          {t('ticket.review.statusEyebrow')}
                        </label>
                        <select
                          id="status-update-select"
                          aria-label={t('ticket.review.newStatus')}
                          className="ticket-detail__control-select"
                          value={pendingStatus || ticket.status}
                          onChange={(event) => {
                            setPendingStatus(event.target.value as TicketStatus);
                            setStatusUpdateError(null);
                          }}
                          disabled={isSavingChanges}
                        >
                          {getSelectableTicketStatuses(ticket.status).map((status) => (
                            <option key={status} value={status}>
                              {formatStatus(status)}
                            </option>
                          ))}
                        </select>
                      </div>
                      {pendingOutcomeKind && (
                        <div className="ticket-detail__control-row">
                          <label htmlFor="status-reason-select">
                            {t('ticket.review.requiredReason')}
                          </label>
                          <select
                            id="status-reason-select"
                            className="ticket-detail__control-select"
                            value={statusReasonCode}
                            onChange={(event) => {
                              setStatusReasonCode(event.target.value);
                              setStatusUpdateError(null);
                            }}
                            disabled={isSavingChanges}
                          >
                            <option value="">{t('ticket.review.selectReason')}</option>
                            {reasonsForKind(pendingOutcomeKind).map((reason) => (
                              <option key={reason.code} value={reason.code}>
                                {reason.label}
                              </option>
                            ))}
                          </select>
                          <label htmlFor="status-private-note">
                            {t('ticket.review.privateNote')}
                          </label>
                          <input
                            id="status-private-note"
                            className="ticket-detail__control-select"
                            value={statusPrivateNote}
                            maxLength={500}
                            onChange={(event) => setStatusPrivateNote(event.target.value)}
                            disabled={isSavingChanges}
                          />
                        </div>
                      )}
                      {ticket.outcome && (
                        <p className="ticket-detail__card-hint">
                          {t('ticket.review.recordedOutcome')}
                          {ticket.outcome.resolutionReasonCode
                            ? t('ticket.review.recordedOutcomeCode', {
                                code: ticket.outcome.resolutionReasonCode,
                              })
                            : ''}
                          {ticket.outcome.closureReasonCode
                            ? t('ticket.review.closedCode', {
                                code: ticket.outcome.closureReasonCode,
                              })
                            : ''}
                          {ticket.outcome.resolutionNote
                            ? t('ticket.review.privateNoteOnFile')
                            : ''}
                        </p>
                      )}
                      {statusUpdateError && (
                        <p className="ticket-detail__status-error" role="alert">
                          {statusUpdateError}
                        </p>
                      )}
                    </div>

                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__eyebrow">
                        {t('ticket.review.departmentEyebrow')}
                      </p>
                      <div className="ticket-detail__department-current">
                        <span className="ticket-detail__department">
                          {ticket.departmentName ?? formatDepartment(ticket.departmentId)}
                        </span>
                      </div>

                      <div className="ticket-detail__control-row">
                        <label htmlFor="department-assign-select">
                          {t('ticket.review.departmentEyebrow')}
                        </label>
                        <select
                          id="department-assign-select"
                          aria-label={t('ticket.review.assignedDepartment')}
                          className="ticket-detail__control-select"
                          value={selectedDepartmentId}
                          onChange={(event) => {
                            setSelectedDepartmentId(event.target.value);
                            setDepartmentUpdateError(null);
                          }}
                          disabled={isSavingChanges}
                        >
                          <option value="">{t('ticket.review.selectDepartment')}</option>
                          {DEPARTMENT_OPTIONS.map((department) => (
                            <option key={department.departmentId} value={department.departmentId}>
                              {department.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      {ticket.ai?.suggestedDepartmentId &&
                        ticket.ai.suggestedDepartmentId !== selectedDepartmentId && (
                          <small className="ticket-detail__field-suggestion">
                            <span className="ticket-detail__ai-icon" aria-hidden="true">
                              <IconSparkles />
                            </span>
                            {t('ticket.review.suggested', {
                              department: formatDepartment(ticket.ai.suggestedDepartmentId),
                            })}
                          </small>
                        )}

                      {departmentUpdateError && (
                        <p className="ticket-detail__status-error" role="alert">
                          {departmentUpdateError}
                        </p>
                      )}
                      {ticket.updatedBy && ticket.departmentId && (
                        <small className="ticket-detail__department-actor">
                          {t('ticket.review.lastUpdatedBy', { name: ticket.updatedBy })}
                          {ticket.updatedAt ? (
                            <>
                              {' '}
                              {t('ticket.review.on')}{' '}
                              <time dateTime={ticket.updatedAt}>
                                {formatCreatedDate(ticket.updatedAt)}
                              </time>
                            </>
                          ) : null}
                        </small>
                      )}
                    </div>

                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__eyebrow">{t('ticket.review.fieldAssignment')}</p>
                      <div className="ticket-detail__control-row">
                        <label htmlFor="workforce-assign-select">
                          {t('ticket.review.assignedWorkerOrTeam')}
                        </label>
                        <select
                          id="workforce-assign-select"
                          className="ticket-detail__control-select"
                          value={selectedWorkforceValue}
                          onChange={(event) => {
                            setSelectedWorkforceValue(event.target.value);
                            setWorkforceError(null);
                          }}
                          disabled={isSavingChanges}
                        >
                          <option value="">{t('ticket.review.unassigned')}</option>
                          {workers
                            .filter(
                              (worker) =>
                                worker.workerId === ticket.assignedWorkerId ||
                                (worker.active &&
                                  (!ticket.departmentId ||
                                    worker.departmentIds.includes(ticket.departmentId))),
                            )
                            .map((worker) => (
                              <option key={worker.workerId} value={`worker:${worker.workerId}`}>
                                {worker.active
                                  ? t('ticket.review.workerOption', { name: worker.displayName })
                                  : t('ticket.review.workerInactive', { name: worker.displayName })}
                              </option>
                            ))}
                          {teams
                            .filter(
                              (team) =>
                                team.teamId === ticket.assignedTeamId ||
                                (team.active &&
                                  (!ticket.departmentId ||
                                    team.departmentIds.includes(ticket.departmentId))),
                            )
                            .map((team) => (
                              <option key={team.teamId} value={`team:${team.teamId}`}>
                                {team.active
                                  ? t('ticket.review.teamOption', { name: team.displayName })
                                  : t('ticket.review.teamInactive', { name: team.displayName })}
                              </option>
                            ))}
                        </select>
                      </div>
                      {workforceError && (
                        <p className="ticket-detail__status-error" role="alert">
                          {workforceError}
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                <div
                  className={`ticket-detail__card ticket-detail__card--work-order${activeWorkOrder ? ' ticket-detail__card--work-order-active' : ' ticket-detail__card--work-order-create'}`}
                >
                  <div className="ticket-detail__compact-heading">
                    <h4 className="ticket-detail__card-title">{t('ticket.workOrder.title')}</h4>
                    <span
                      className="ticket-detail__compact-info"
                      tabIndex={0}
                      aria-label={t('ticket.workOrder.hint')}
                    >
                      ⓘ<span role="tooltip">{t('ticket.workOrder.hint')}</span>
                    </span>
                  </div>
                  {activeWorkOrder ? (
                    <div className="ticket-detail__action-group">
                      <p className="ticket-detail__current-value">
                        {t('ticket.workOrder.current', {
                          state: formatWorkOrderState(activeWorkOrder.state),
                          id: activeWorkOrder.workOrderId,
                        })}
                      </p>
                      <p className="ticket-detail__card-hint">{activeWorkOrder.summary}</p>
                      <div className="ticket-detail__evidence-groups">
                        <section aria-labelledby="citizen-report-evidence-heading">
                          <h5
                            id="citizen-report-evidence-heading"
                            className="ticket-detail__card-title"
                          >
                            {t('ticket.workOrder.citizenEvidence')}
                          </h5>
                          <p className="ticket-detail__card-hint">
                            {t('ticket.workOrder.citizenEvidenceHint')}
                          </p>
                          <EvidencePhotoList
                            items={
                              citizenOriginalEvidence.length
                                ? citizenOriginalEvidence
                                : ticket
                                  ? [
                                      {
                                        evidenceId: 'citizen-original',
                                        ticketId: ticket.ticketId,
                                        workOrderId: activeWorkOrder.workOrderId,
                                        kind: 'ORIGINAL_REPORT',
                                        objectKey: ticket.imageObjectKey,
                                        contentType: 'image/jpeg',
                                        uploadedBy: 'citizen',
                                        createdAt: ticket.createdAt,
                                        source: 'TICKET_ORIGINAL',
                                        photoUrl: ticket.imageUrl,
                                      } satisfies WorkOrderEvidence,
                                    ]
                                  : []
                            }
                            emptyLabel={t('ticket.workOrder.noCitizenPhoto')}
                            category={ticket?.category ?? 'PENDING_CLASSIFICATION'}
                          />
                        </section>
                        <section aria-labelledby="maintenance-before-heading">
                          <h5 id="maintenance-before-heading" className="ticket-detail__card-title">
                            {t('ticket.workOrder.beforeTitle')}
                          </h5>
                          <EvidencePhotoList
                            items={beforeEvidence}
                            emptyLabel={t('ticket.workOrder.noBefore')}
                            category={ticket?.category ?? 'PENDING_CLASSIFICATION'}
                          />
                          <label className="ticket-detail__card-hint" htmlFor="wo-before-upload">
                            {t('ticket.workOrder.uploadBefore')}
                          </label>
                          <input
                            id="wo-before-upload"
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            disabled={isUploadingEvidence || isMutatingWorkOrder}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.target.value = '';
                              void handleEvidenceUpload(
                                activeWorkOrder.workOrderId,
                                'BEFORE',
                                file,
                              );
                            }}
                          />
                        </section>
                        <section aria-labelledby="maintenance-after-heading">
                          <h5 id="maintenance-after-heading" className="ticket-detail__card-title">
                            {t('ticket.workOrder.afterTitle')}
                          </h5>
                          <EvidencePhotoList
                            items={afterEvidence}
                            emptyLabel={t('ticket.workOrder.noAfter')}
                            category={ticket?.category ?? 'PENDING_CLASSIFICATION'}
                          />
                          <label className="ticket-detail__card-hint" htmlFor="wo-after-upload">
                            {t('ticket.workOrder.uploadAfter')}
                          </label>
                          <input
                            id="wo-after-upload"
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            disabled={isUploadingEvidence || isMutatingWorkOrder}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.target.value = '';
                              void handleEvidenceUpload(activeWorkOrder.workOrderId, 'AFTER', file);
                            }}
                          />
                        </section>
                      </div>
                      <div className="ticket-detail__control-row">
                        <label htmlFor="active-work-order-assignee">
                          {t('ticket.workOrder.assignee')}
                        </label>
                        <select
                          id="active-work-order-assignee"
                          className="ticket-detail__control-select"
                          value={workOrderAssignee}
                          onChange={(event) => setWorkOrderAssignee(event.target.value)}
                          disabled={isMutatingWorkOrder}
                        >
                          <option value="">{t('ticket.review.unassigned')}</option>
                          {activeWorkOrder.assignedWorkerId &&
                            !workers.some(
                              (worker) => worker.workerId === activeWorkOrder.assignedWorkerId,
                            ) && (
                              <option value={`worker:${activeWorkOrder.assignedWorkerId}`}>
                                {t('ticket.review.workerOption', {
                                  name: activeWorkOrder.assignedWorkerId,
                                })}
                              </option>
                            )}
                          {activeWorkOrder.assignedTeamId &&
                            !teams.some(
                              (team) => team.teamId === activeWorkOrder.assignedTeamId,
                            ) && (
                              <option value={`team:${activeWorkOrder.assignedTeamId}`}>
                                {t('ticket.review.teamOption', {
                                  name: activeWorkOrder.assignedTeamId,
                                })}
                              </option>
                            )}
                          {workers
                            .filter((worker) => worker.active)
                            .map((worker) => (
                              <option key={worker.workerId} value={`worker:${worker.workerId}`}>
                                {t('ticket.review.workerOption', { name: worker.displayName })}
                              </option>
                            ))}
                          {teams
                            .filter((team) => team.active)
                            .map((team) => (
                              <option key={team.teamId} value={`team:${team.teamId}`}>
                                {t('ticket.review.teamOption', { name: team.displayName })}
                              </option>
                            ))}
                        </select>
                        <div className="ticket-detail__control-buttons">
                          <button
                            type="button"
                            className="ticket-detail__review-button ticket-detail__review-button--secondary"
                            disabled={isMutatingWorkOrder}
                            onClick={() =>
                              void runWorkOrderMutation(
                                () =>
                                  assignWorkOrder(
                                    activeWorkOrder.workOrderId,
                                    workOrderAssignee === ''
                                      ? { clear: true }
                                      : workOrderAssignee.startsWith('team:')
                                        ? { teamId: workOrderAssignee.slice('team:'.length) }
                                        : { workerId: workOrderAssignee.slice('worker:'.length) },
                                  ),
                                t('ticket.workOrder.assignmentUpdated'),
                              )
                            }
                          >
                            {t('ticket.workOrder.saveAssignment')}
                          </button>
                        </div>
                      </div>
                      <div className="ticket-detail__control-buttons">
                        {activeWorkOrder.state !== 'IN_PROGRESS' && (
                          <button
                            type="button"
                            className="ticket-detail__review-button"
                            disabled={isMutatingWorkOrder}
                            onClick={() =>
                              void runWorkOrderMutation(
                                () => startWorkOrder(activeWorkOrder.workOrderId),
                                t('ticket.workOrder.started'),
                              )
                            }
                          >
                            {t('ticket.workOrder.startWork')}
                          </button>
                        )}
                        {activeWorkOrder.state === 'IN_PROGRESS' && (
                          <button
                            type="button"
                            className="ticket-detail__review-button"
                            disabled={isMutatingWorkOrder || !canCompleteWorkOrder}
                            onClick={() =>
                              void runWorkOrderMutation(
                                () => completeWorkOrder(activeWorkOrder.workOrderId, workOrderNote),
                                t('ticket.workOrder.completed'),
                              )
                            }
                          >
                            {t('ticket.workOrder.completeWork')}
                          </button>
                        )}
                      </div>
                      <div className="ticket-detail__control-row">
                        <label htmlFor="work-order-cancel-reason">
                          {t('ticket.workOrder.cancelReason')}
                        </label>
                        <select
                          id="work-order-cancel-reason"
                          className="ticket-detail__control-select"
                          value={workOrderCancelReason}
                          onChange={(event) => setWorkOrderCancelReason(event.target.value)}
                          disabled={isMutatingWorkOrder}
                        >
                          <option value="">{t('ticket.workOrder.selectCancelReason')}</option>
                          {workOrderCancelReasons().map((reason) => (
                            <option key={reason.code} value={reason.code}>
                              {reason.label}
                            </option>
                          ))}
                        </select>
                        <label htmlFor="work-order-note">{t('ticket.review.privateNote')}</label>
                        <input
                          id="work-order-note"
                          className="ticket-detail__control-select"
                          value={workOrderNote}
                          maxLength={500}
                          onChange={(event) => setWorkOrderNote(event.target.value)}
                          disabled={isMutatingWorkOrder}
                        />
                        <div className="ticket-detail__control-buttons">
                          <button
                            type="button"
                            className="ticket-detail__review-button ticket-detail__review-button--secondary"
                            disabled={isMutatingWorkOrder || !workOrderCancelReason}
                            onClick={() =>
                              void runWorkOrderMutation(
                                () =>
                                  cancelWorkOrder(
                                    activeWorkOrder.workOrderId,
                                    workOrderCancelReason,
                                    workOrderNote,
                                  ),
                                t('ticket.workOrder.cancelled'),
                              )
                            }
                          >
                            {t('ticket.workOrder.cancelWorkOrder')}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="ticket-detail__action-group">
                      <div className="ticket-detail__control-row">
                        <label htmlFor="work-order-summary">{t('ticket.workOrder.summary')}</label>
                        <input
                          id="work-order-summary"
                          className="ticket-detail__control-select"
                          value={workOrderSummary}
                          maxLength={500}
                          placeholder={t('ticket.workOrder.summaryPlaceholder')}
                          onChange={(event) => setWorkOrderSummary(event.target.value)}
                          disabled={isMutatingWorkOrder}
                        />
                        <label htmlFor="work-order-assignee">
                          {t('ticket.workOrder.assignWorkerOrTeam')}
                        </label>
                        <select
                          id="work-order-assignee"
                          className="ticket-detail__control-select"
                          value={workOrderAssignee}
                          onChange={(event) => setWorkOrderAssignee(event.target.value)}
                          disabled={isMutatingWorkOrder}
                        >
                          <option value="">{t('ticket.review.unassigned')}</option>
                          {workers
                            .filter((worker) => worker.active)
                            .map((worker) => (
                              <option key={worker.workerId} value={`worker:${worker.workerId}`}>
                                {t('ticket.review.workerOption', { name: worker.displayName })}
                              </option>
                            ))}
                          {teams
                            .filter((team) => team.active)
                            .map((team) => (
                              <option key={team.teamId} value={`team:${team.teamId}`}>
                                {t('ticket.review.teamOption', { name: team.displayName })}
                              </option>
                            ))}
                        </select>
                        <div className="ticket-detail__control-buttons">
                          <button
                            type="button"
                            className="ticket-detail__review-button"
                            disabled={isMutatingWorkOrder}
                            onClick={() => void handleCreateWorkOrder()}
                          >
                            {isMutatingWorkOrder
                              ? t('ticket.workOrder.saving')
                              : t('ticket.workOrder.create')}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                  {workOrders.length > 1 && (
                    <p className="ticket-detail__card-hint">
                      {t('ticket.workOrder.countHint', { count: workOrders.length })}
                    </p>
                  )}
                  {workOrderSuccess && (
                    <p className="ticket-detail__status-message" role="status">
                      {workOrderSuccess}
                    </p>
                  )}
                  {workOrderError && (
                    <p className="ticket-detail__status-error" role="alert">
                      {workOrderError}
                    </p>
                  )}
                </div>

                {resolutionFeedback?.status ? (
                  <div className="ticket-detail__card">
                    <h4 className="ticket-detail__card-title">{t('ticket.feedback.title')}</h4>
                    <p className="ticket-detail__current-value">
                      {resolutionFeedback.status === 'CONFIRMED_FIXED'
                        ? t('ticket.feedback.confirmedFixed')
                        : t('ticket.feedback.stillUnresolved')}
                    </p>
                    {resolutionFeedback.note ? (
                      <p className="ticket-detail__card-hint">
                        {t('ticket.feedback.privateNote', { note: resolutionFeedback.note })}
                      </p>
                    ) : null}
                    {resolutionFeedback.needsReview ? (
                      <div className="ticket-detail__control-buttons">
                        <button
                          type="button"
                          className="ticket-detail__review-button"
                          disabled={isReviewingFeedback}
                          onClick={() => void handleFeedbackReview('KEEP_RESOLVED')}
                        >
                          {t('ticket.feedback.keepResolved')}
                        </button>
                        <button
                          type="button"
                          className="ticket-detail__review-button ticket-detail__review-button--secondary"
                          disabled={isReviewingFeedback}
                          onClick={() => void handleFeedbackReview('RETURN_IN_PROGRESS')}
                        >
                          {t('ticket.feedback.returnInProgress')}
                        </button>
                      </div>
                    ) : resolutionFeedback.reviewAction ? (
                      <p className="ticket-detail__card-hint">
                        {t('ticket.feedback.reviewed', {
                          action: resolutionFeedback.reviewAction
                            .replaceAll('_', ' ')
                            .toLowerCase(),
                        })}
                      </p>
                    ) : null}
                    {feedbackError ? (
                      <p className="ticket-detail__status-error" role="alert">
                        {feedbackError}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <div className="ticket-detail__card ticket-detail__card--category">
                  <div className="ticket-detail__card-heading-row">
                    <h4 className="ticket-detail__card-title">
                      {t('ticket.review.categoryTitle')}
                    </h4>
                    <span className="ticket-detail__ai-chip">
                      <span className="ticket-detail__ai-icon" aria-hidden="true">
                        <IconSparkles />
                      </span>
                      {t('ticket.review.aiAssisted')}
                    </span>
                  </div>

                  {!ticket.ai && (
                    <p className="ticket-detail__review-notice" role="status">
                      {t('ticket.review.noAi')}
                    </p>
                  )}

                  {ticket.ai?.aiProcessingStatus === 'pending' && (
                    <p className="ticket-detail__review-notice" role="status">
                      {t('ticket.review.aiPending')}
                    </p>
                  )}

                  {ticket.ai?.aiProcessingStatus === 'processing' && (
                    <p className="ticket-detail__review-notice" role="status">
                      {t('ticket.review.aiProcessing')}
                    </p>
                  )}

                  {ticket.ai?.aiProcessingStatus === 'failed' && !ticket.ai.aiSuggestedCategory && (
                    <p
                      className="ticket-detail__review-notice ticket-detail__review-notice--warning"
                      role="status"
                    >
                      {t('ticket.review.aiFailed')}
                    </p>
                  )}

                  {ticket.ai?.aiSuggestedCategory &&
                    ticket.ai.aiSuggestedCategory !==
                      (ticket.ai.finalCategory ?? selectedCategory) && (
                      <div className="ticket-detail__suggestion">
                        <span className="ticket-detail__suggestion-label">
                          {t('ticket.review.aiSuggestion')}
                        </span>
                        <CategoryBadge category={ticket.ai.aiSuggestedCategory} />
                        {ticket.ai.aiConfidence !== undefined && (
                          <span className="ticket-detail__confidence">
                            {t('ticket.review.confidence', {
                              percent: Math.round(ticket.ai.aiConfidence * 100),
                            })}
                          </span>
                        )}
                        {ticket.ai.aiCategoryExplanation && (
                          <span
                            className="ticket-detail__compact-info"
                            tabIndex={0}
                            aria-label={t('ticket.review.aiSuggestion')}
                          >
                            ⓘ<span role="tooltip">{ticket.ai.aiCategoryExplanation}</span>
                          </span>
                        )}
                      </div>
                    )}

                  {ticket.ai?.finalCategory && (
                    <span className="ticket-detail__category-reviewed" role="status">
                      ✓ {t('ticket.review.reviewed')}
                      {ticket.ai.categoryReviewedAt && (
                        <span
                          className="ticket-detail__compact-info"
                          tabIndex={0}
                          aria-label={t('ticket.review.reviewed')}
                        >
                          ⓘ
                          <span role="tooltip">
                            {ticket.ai.categoryReviewedBy
                              ? t('ticket.review.reviewedBy', {
                                  name: ticket.ai.categoryReviewedBy,
                                })
                              : t('ticket.review.reviewed')}{' '}
                            {t('ticket.review.on')}{' '}
                            {formatCreatedDate(ticket.ai.categoryReviewedAt)}
                          </span>
                        </span>
                      )}
                    </span>
                  )}

                  <div className="ticket-detail__control-row">
                    <label htmlFor="category-review-select">
                      {t('ticket.review.finalCategory')}
                    </label>
                    <select
                      id="category-review-select"
                      className="ticket-detail__control-select"
                      value={selectedCategory}
                      onChange={(event) => {
                        setSelectedCategory(event.target.value);
                        setCategoryReviewError(null);
                      }}
                      disabled={isSavingChanges || ticket.ai?.aiProcessingStatus === 'pending'}
                    >
                      <option value="">{t('ticket.review.selectCategory')}</option>
                      {SUPPORTED_CATEGORY_OPTIONS.map((category) => (
                        <option key={category} value={category}>
                          {formatCategory(category)}
                        </option>
                      ))}
                    </select>

                    <div className="ticket-detail__control-buttons">
                      {ticket.ai?.aiSuggestedCategory &&
                        ticket.ai.aiSuggestedCategory !== selectedCategory && (
                          <button
                            type="button"
                            className="ticket-detail__review-button ticket-detail__review-button--secondary"
                            onClick={() =>
                              setSelectedCategory(ticket.ai?.aiSuggestedCategory ?? '')
                            }
                            disabled={isSavingChanges || ticket.ai.aiProcessingStatus === 'pending'}
                          >
                            {t('ticket.review.acceptAi')}
                          </button>
                        )}
                    </div>
                  </div>

                  {categoryReviewError && (
                    <p className="ticket-detail__status-error" role="alert">
                      {categoryReviewError}
                    </p>
                  )}
                </div>

                <div className="ticket-detail__save-bar">
                  <span aria-live="polite">
                    {hasUnsavedChanges
                      ? t('ticket.review.unsavedChanges', { count: unsavedChangeCount })
                      : ''}
                  </span>
                  <button
                    type="button"
                    className="ticket-detail__review-button"
                    disabled={!hasUnsavedChanges || isSavingChanges}
                    onClick={() => void handleSaveChanges()}
                  >
                    {isSavingChanges
                      ? t('ticket.review.savingChanges')
                      : t('ticket.review.saveChanges')}
                  </button>
                </div>
                {saveChangesError && (
                  <p className="ticket-detail__status-error" role="alert">
                    {saveChangesError}
                  </p>
                )}
              </div>

              <aside className="ticket-detail__card ticket-detail__card--privacy-review">
                <h4 className="ticket-detail__card-title">{t('ticket.review.privacyTitle')}</h4>
                <p className="ticket-detail__card-hint">{t('ticket.review.privacyHint')}</p>
                <ImageRedactionReviewPanel
                  ticketId={ticket.ticketId}
                  category={effectiveCategory ?? ticket.category}
                  onChanged={() => {
                    void fetchTicketById(ticket.ticketId).then((next) => {
                      if (next) {
                        setTicket(next);
                      }
                    });
                  }}
                />
              </aside>
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
              <h3 className="sr-only">{t('ticket.duplicates.heading')}</h3>

              <div className="ticket-detail__card">
                <h4 className="ticket-detail__card-title">{t('ticket.duplicates.title')}</h4>
                <p className="ticket-detail__card-hint">{t('ticket.duplicates.hint')}</p>

                {ticket.duplicateGroupId && (
                  <div className="ticket-detail__group-summary" role="status">
                    <p>
                      {ticket.duplicateGroup?.canonicalTicketId === ticket.ticketId
                        ? t('ticket.duplicates.groupedAsMain')
                        : t('ticket.duplicates.grouped')}
                    </p>
                    {ticket.duplicateGroup?.ticketIds && (
                      <ul className="ticket-detail__group-links">
                        {ticket.duplicateGroup.ticketIds.map((memberId) => (
                          <li key={memberId}>
                            {memberId === ticket.ticketId ? (
                              <span>
                                {memberId === ticket.duplicateGroup?.canonicalTicketId
                                  ? t('ticket.duplicates.mainPrefix')
                                  : ''}
                                {t('ticket.duplicates.currentTicket')}
                              </span>
                            ) : (
                              <Link to={`/tickets/${memberId}`}>
                                {memberId === ticket.duplicateGroup?.canonicalTicketId
                                  ? t('ticket.duplicates.mainPrefix')
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
                        {t('ticket.duplicates.addFromMain')}
                      </p>
                    )}
                  </div>
                )}

                {effectiveCategory === null ? (
                  <p className="ticket-detail__merge-empty">
                    {t('ticket.duplicates.unclassified')}
                  </p>
                ) : (
                  <>
                    <div className="ticket-detail__candidate-toolbar">
                      <label htmlFor="duplicate-filter">{t('ticket.duplicates.search')}</label>
                      <input
                        id="duplicate-filter"
                        type="search"
                        className="ticket-detail__filter-input"
                        value={candidateFilter}
                        onChange={(event) => setCandidateFilter(event.target.value)}
                        placeholder={t('ticket.duplicates.searchPlaceholder')}
                      />
                      <p className="ticket-detail__candidate-count" role="status">
                        {candidateLoadState === 'loading'
                          ? t('ticket.duplicates.searching')
                          : t(
                              candidateNextCursor
                                ? duplicateCandidates.length === 1
                                  ? 'ticket.duplicates.showingSoFar'
                                  : 'ticket.duplicates.showingPluralSoFar'
                                : duplicateCandidates.length === 1
                                  ? 'ticket.duplicates.showing'
                                  : 'ticket.duplicates.showingPlural',
                              { count: duplicateCandidates.length },
                            )}
                      </p>
                    </div>

                    {candidateLoadState === 'error' && (
                      <div className="ticket-detail__comparison-error">
                        <p className="ticket-detail__status-error" role="alert">
                          {candidateError ?? t('ticket.duplicates.unableLoad')}
                        </p>
                        <button
                          type="button"
                          className="ticket-detail__review-button ticket-detail__review-button--secondary"
                          onClick={() => setRefreshToken((current) => current + 1)}
                        >
                          {t('ticket.duplicates.retrySearch')}
                        </button>
                      </div>
                    )}

                    {candidateLoadState === 'ready' && duplicateCandidates.length === 0 && (
                      <p className="ticket-detail__merge-empty">
                        {candidateQuery
                          ? t('ticket.duplicates.noMatch')
                          : t('ticket.duplicates.noneFound')}
                      </p>
                    )}

                    {selectedCandidates.length > 1 && (
                      <div className="ticket-detail__compare-selected">
                        <h5 className="ticket-detail__subsection-title">
                          {t('ticket.duplicates.compareSelected', {
                            count: selectedCandidates.length,
                          })}
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
                                  : t('ticket.duplicates.distanceUnknown')}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <ul className="ticket-detail__candidates">
                      {duplicateCandidates.map((candidate) => {
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
                                  onChange={() => toggleDuplicateSelection(candidate)}
                                  disabled={isMerging}
                                  aria-label={t('ticket.duplicates.selectAria', {
                                    ticketNumber: candidate.ticketNumber,
                                  })}
                                />
                              )}

                              <CandidateThumb
                                ticketNumber={candidate.ticketNumber}
                                category={candidate.category}
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
                                      {t('ticket.duplicates.suggestedMatch')}
                                    </span>
                                  )}
                                  {!candidate.mergeable && (
                                    <span className="ticket-detail__match-hint">
                                      {t('ticket.duplicates.notMergeable')}
                                    </span>
                                  )}
                                </div>

                                <p className="ticket-detail__candidate-excerpt">
                                  {describeExcerpt(candidate.summary)}
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
                                      {t('ticket.duplicates.ageOld', {
                                        age: formatTicketAge(candidate.createdAt),
                                      })}
                                      <time dateTime={candidate.createdAt}>
                                        {formatCreatedDate(candidate.createdAt)}
                                      </time>
                                    </span>
                                  )}
                                  <span>
                                    {candidate.location.addressText.trim() ||
                                      t('ticket.duplicates.locationMissing')}
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
                                  ? t('ticket.duplicates.hideComparison', {
                                      ticketNumber: candidate.ticketNumber,
                                    })
                                  : t('ticket.duplicates.compare', {
                                      ticketNumber: candidate.ticketNumber,
                                    })}
                              </button>
                            </div>

                            {isExpanded && (
                              <div
                                id={panelId}
                                className="ticket-detail__comparison"
                                role="region"
                                aria-label={t('ticket.duplicates.comparisonAria', {
                                  ticketNumber: candidate.ticketNumber,
                                  currentTicketNumber: ticket.ticketNumber,
                                })}
                              >
                                {(!comparison || comparison.status === 'loading') && (
                                  <p className="ticket-detail__status-message" role="status">
                                    {t('ticket.duplicates.loadingComparison')}
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
                                      {t('ticket.duplicates.retryComparison')}
                                    </button>
                                  </div>
                                )}

                                {comparison?.status === 'ready' && currentComparison && (
                                  <>
                                    <div className="ticket-detail__comparison-grid">
                                      <ComparisonColumn
                                        eyebrow={t('ticket.duplicates.currentTicketEyebrow')}
                                        heading={currentComparison.ticketNumber}
                                        data={currentComparison}
                                      />
                                      <ComparisonColumn
                                        eyebrow={t('ticket.duplicates.candidateEyebrow')}
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
                                          ? t('ticket.duplicates.distanceUnavailable')
                                          : t('ticket.duplicates.reportedDistance', {
                                              distance: formatDistanceMeters(distance),
                                            });
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

                    {candidateNextCursor && (
                      <div className="ticket-detail__candidate-more">
                        <button
                          type="button"
                          className="ticket-detail__ghost-button"
                          onClick={() => void handleLoadMoreCandidates()}
                          disabled={isLoadingMoreCandidates}
                        >
                          {isLoadingMoreCandidates
                            ? t('ticket.duplicates.loadingMore')
                            : t('ticket.duplicates.loadMore')}
                        </button>
                        <p className="ticket-detail__merge-help">
                          {t('ticket.duplicates.moreHelp')}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {isCanonicalTicket && effectiveCategory !== null && (
                  <div className="ticket-detail__merge-controls">
                    <p className="ticket-detail__merge-help">
                      {ticket.duplicateGroupId
                        ? t('ticket.duplicates.addMore')
                        : t('ticket.duplicates.chooseOthers')}
                    </p>
                    {unresolvedSelectionCount > 0 && (
                      <p className="ticket-detail__merge-help" role="status">
                        {failedSelectionCount > 0
                          ? t(
                              failedSelectionCount === 1
                                ? 'ticket.duplicates.comparisonFailed'
                                : 'ticket.duplicates.comparisonFailedPlural',
                              { count: failedSelectionCount },
                            )
                          : t(
                              unresolvedSelectionCount === 1
                                ? 'ticket.duplicates.loadingSelection'
                                : 'ticket.duplicates.loadingSelectionPlural',
                              { count: unresolvedSelectionCount },
                            )}
                      </p>
                    )}
                    <button
                      type="button"
                      className="ticket-detail__review-button"
                      onClick={() => setIsMergeDialogOpen(true)}
                      disabled={isMerging || !canMergeSelection}
                    >
                      {isMerging
                        ? t('ticket.duplicates.merging')
                        : t('ticket.duplicates.mergeSelected')}
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
              <h3 className="sr-only">{t('ticket.activity.heading')}</h3>

              <div className="ticket-detail__card">
                <h4 className="ticket-detail__card-title">{t('ticket.activity.title')}</h4>
                <p className="ticket-detail__card-hint">{t('ticket.activity.hint')}</p>
                {activityLoading && internalActivity.length === 0 && (
                  <p role="status">{t('ticket.activity.loading')}</p>
                )}
                {!activityLoading &&
                  !commentsLoading &&
                  !activityError &&
                  !commentsError &&
                  unifiedInternalActivity.length === 0 && (
                    <p className="ticket-detail__merge-empty">{t('ticket.activity.empty')}</p>
                  )}
                {unifiedInternalActivity.length > 0 && (
                  <ol
                    className="ticket-detail__activity"
                    aria-label={t('ticket.activity.listA11y')}
                  >
                    {unifiedInternalActivity.map(({ event, comment }) => (
                      <li key={event.eventId} className="ticket-detail__activity-item">
                        <span className="ticket-detail__activity-marker" aria-hidden="true" />
                        <div className="ticket-detail__activity-body">
                          <div className="ticket-detail__activity-heading">
                            <span className="ticket-detail__activity-title">
                              {comment
                                ? t('ticket.activity.internalComment')
                                : event.eventType.replaceAll('_', ' ')}
                            </span>
                            <time
                              className="ticket-detail__activity-time"
                              dateTime={event.occurredAt}
                            >
                              {formatCreatedDate(event.occurredAt)}
                            </time>
                          </div>
                          {comment ? (
                            <>
                              <p className="ticket-detail__activity-detail">{comment.text}</p>
                              {comment.mentionedStaffIds.length > 0 && (
                                <p>
                                  {t('ticket.activity.mentioned', {
                                    ids: comment.mentionedStaffIds.join(', '),
                                  })}
                                </p>
                              )}
                            </>
                          ) : (
                            event.details.summary && (
                              <p className="ticket-detail__activity-detail">
                                {event.details.summary}
                              </p>
                            )
                          )}
                          {event.actorDisplayName && (
                            <p className="ticket-detail__activity-actor">
                              {t('ticket.activity.byActor', { name: event.actorDisplayName })}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
                {activityError && (
                  <p className="ticket-detail__status-error" role="alert">
                    {activityError}{' '}
                    <button
                      type="button"
                      className="ticket-detail__ghost-button"
                      onClick={() => setActivityRefreshKey((value) => value + 1)}
                    >
                      {t('ticket.activity.retry')}
                    </button>
                  </p>
                )}
                {loadMoreActivityError && (
                  <p className="ticket-detail__status-error" role="alert">
                    {loadMoreActivityError}
                  </p>
                )}
                {nextActivityCursor && (
                  <button
                    type="button"
                    className="ticket-detail__ghost-button"
                    onClick={() => void loadMoreActivity()}
                    disabled={isLoadingMoreActivity}
                  >
                    {isLoadingMoreActivity
                      ? t('ticket.activity.loadingMore')
                      : t('ticket.activity.loadMore')}
                  </button>
                )}

                {commentsLoading && comments.length === 0 && (
                  <p role="status">{t('ticket.comments.loading')}</p>
                )}
                {commentsError && (
                  <p className="ticket-detail__status-error" role="alert">
                    {commentsError}{' '}
                    <button
                      type="button"
                      className="ticket-detail__ghost-button"
                      onClick={() => setCommentsRefreshKey((value) => value + 1)}
                    >
                      {t('ticket.comments.retry')}
                    </button>
                  </p>
                )}
                <form
                  className="ticket-detail__comment-composer"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCommentSubmit();
                  }}
                >
                  <label htmlFor="internal-comment">{t('ticket.comments.add')}</label>
                  <textarea
                    id="internal-comment"
                    className="ticket-detail__comment-input"
                    value={commentText}
                    onChange={(event) => setCommentText(event.target.value)}
                    maxLength={2000}
                    rows={4}
                    placeholder={t('ticket.comments.placeholder')}
                  />
                  <div className="ticket-detail__comment-actions">
                    <button
                      type="submit"
                      className="ticket-detail__review-button"
                      disabled={isSubmittingComment || !commentText.trim()}
                    >
                      {isSubmittingComment
                        ? t('ticket.comments.posting')
                        : t('ticket.comments.post')}
                    </button>
                  </div>
                  {commentError && (
                    <p className="ticket-detail__status-error" role="alert">
                      {commentError}
                    </p>
                  )}
                </form>
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
                  {t('ticket.duplicates.confirmTitle')}
                </h4>
                <p id="merge-confirm-description" className="ticket-detail__modal-text">
                  {t('ticket.duplicates.confirmBody', { ticketNumber: ticket.ticketNumber })}
                </p>
                <ul className="ticket-detail__modal-list">
                  {selectedCandidates.map((candidate) => (
                    <li key={candidate.ticketId}>
                      {t('ticket.duplicates.becomesDuplicate', {
                        ticketNumber: candidate.ticketNumber,
                        canonicalTicketNumber: ticket.ticketNumber,
                      })}
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
                    {t('common.cancel')}
                  </button>
                  <button
                    type="button"
                    ref={confirmMergeRef}
                    className="ticket-detail__review-button ticket-detail__review-button--danger"
                    onClick={() => void handleMergeDuplicates()}
                    disabled={isMerging || !canMergeSelection}
                  >
                    {isMerging
                      ? t('ticket.duplicates.merging')
                      : t('ticket.duplicates.confirmMerge')}
                  </button>
                </div>
              </div>
            </div>
          )}

          {pendingLeaveAction && (
            <div className="ticket-detail__modal-backdrop">
              <div
                className="ticket-detail__modal"
                role="dialog"
                aria-modal="true"
                aria-labelledby="unsaved-changes-title"
                aria-describedby="unsaved-changes-prompt"
              >
                <h4 id="unsaved-changes-title" className="ticket-detail__modal-title">
                  {t('ticket.review.unsavedTitle')}
                </h4>
                <p id="unsaved-changes-prompt" className="ticket-detail__modal-text">
                  {t('ticket.review.unsavedPrompt')}
                </p>
                <div className="ticket-detail__modal-actions">
                  <button
                    type="button"
                    className="ticket-detail__ghost-button"
                    onClick={() => {
                      const action = pendingLeaveAction;
                      discardPendingChanges();
                      setPendingLeaveAction(null);
                      action();
                    }}
                  >
                    {t('ticket.review.discardChanges')}
                  </button>
                  <button
                    type="button"
                    className="ticket-detail__ghost-button"
                    onClick={() => setPendingLeaveAction(null)}
                  >
                    {t('ticket.review.stay')}
                  </button>
                  <button
                    type="button"
                    className="ticket-detail__review-button"
                    disabled={isSavingChanges}
                    onClick={() => {
                      const action = pendingLeaveAction;
                      void handleSaveChanges().then((saved) => {
                        if (saved) {
                          setPendingLeaveAction(null);
                          action();
                        }
                      });
                    }}
                  >
                    {isSavingChanges
                      ? t('ticket.review.savingChanges')
                      : t('ticket.review.saveAndLeave')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  if (embedded) {
    return workspace;
  }

  return (
    <DashboardLayout
      title={t('ticket.details')}
      subtitle={
        ticket ? `${ticket.ticketNumber} · ${formatStatus(ticket.status)}` : t('ticket.workspace')
      }
    >
      {workspace}
    </DashboardLayout>
  );
}

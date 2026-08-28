import { useEffect, useMemo, useRef, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import type { TicketAggregates } from '@/types/ticketCollection';
import {
  fetchTicketAggregates,
  fetchTicketById,
  fetchTicketsPage,
  type FetchTicketsFilters,
} from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketTable } from '@/components/TicketTable';
import { BulkTicketAssignmentBar } from '@/components/BulkTicketAssignmentBar';
import { QueueViewsSidebar, type QueueViewId } from '@/components/QueueViewsSidebar';
import { TicketPreviewPanel } from '@/components/TicketPreviewPanel';
import { CategoryDistributionChart } from '@/components/CategoryDistributionChart';
import { DepartmentSummary } from '@/components/DepartmentSummary';
import {
  TicketFilters,
  type ContentSafetyFilter,
  type SlaFilter,
} from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { useI18n } from '@/i18n/LocaleProvider';
import { useDashboardLocationSync } from '@/hooks/useDashboardLocationSync';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import {
  parseDashboardSearchParams,
  type DashboardNavigationFilters,
} from '@/utils/dashboardNavigation';
import {
  getCategoryFilterOptions,
  type CategoryFilter,
  type DepartmentFilter,
  type QueueAttentionStats,
  type StatusFilter,
  type UrgencyFilter,
} from '@/utils/ticketStats';
import './TicketListPage.css';

type LoadState = 'loading' | 'success' | 'error';

const FILTER_DEBOUNCE_MS = import.meta.env.MODE === 'test' ? 0 : 300;

function aggregatesToAttentionStats(aggregates: TicketAggregates | null): QueueAttentionStats {
  return {
    critical: aggregates?.criticalCount ?? 0,
    unassigned: aggregates?.unassignedCount ?? 0,
    aging: aggregates?.overdueCount ?? 0,
  };
}

function buildServerFilters(input: {
  status: StatusFilter;
  category: CategoryFilter;
  urgency: UrgencyFilter;
  department: DepartmentFilter;
  sla: SlaFilter;
  queueView: QueueViewId;
  search: string;
  urgencyCsv?: string | null;
  openOnly?: boolean;
  ticketIds?: string[];
  workerId?: string;
  teamId?: string;
  contentSafetyStatus?: ContentSafetyFilter;
}): FetchTicketsFilters {
  const filters: FetchTicketsFilters = {
    status: input.status,
    category: input.category,
    urgency: input.urgencyCsv || input.urgency,
    departmentId: input.department,
    slaState: input.sla,
    q: input.search.trim() || undefined,
    openOnly: input.openOnly || undefined,
    ticketIds: input.ticketIds?.length ? input.ticketIds : undefined,
    workerId: input.workerId,
    teamId: input.teamId,
    contentSafetyStatus:
      input.contentSafetyStatus && input.contentSafetyStatus !== 'ALL'
        ? input.contentSafetyStatus
        : undefined,
  };

  if (input.queueView === 'unassigned') {
    filters.assignmentState = 'unassigned';
    filters.openOnly = true;
  }
  if (input.queueView === 'aging') {
    // "Overdue" attention view maps to the indexed/bounded slaState contract.
    filters.slaState = 'overdue';
  }
  if (input.queueView === 'critical') {
    filters.urgency = 'critical';
    filters.openOnly = true;
  }
  if (input.queueView === 'high') {
    filters.urgency = 'high';
    filters.openOnly = true;
  }

  return filters;
}

function queueViewFromNavigation(filters: DashboardNavigationFilters): QueueViewId {
  if (filters.assignmentState === 'unassigned') {
    return 'unassigned';
  }
  if (filters.slaState === 'overdue') {
    return 'aging';
  }
  if (filters.urgency === 'critical') {
    return 'critical';
  }
  if (filters.urgency === 'high') {
    return 'high';
  }
  return 'all';
}

export function TicketListPage() {
  const { t } = useI18n();
  const initialFilters = parseDashboardSearchParams(new URLSearchParams(window.location.search));
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [pageTickets, setPageTickets] = useState<Ticket[]>([]);
  const [baselineTickets, setBaselineTickets] = useState<Ticket[]>([]);
  const [aggregates, setAggregates] = useState<TicketAggregates | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    (initialFilters.status as StatusFilter) ?? 'ALL',
  );
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>(
    initialFilters.category ?? 'ALL',
  );
  const [urgencyFilter, setUrgencyFilter] = useState<UrgencyFilter>(
    initialFilters.urgency && !initialFilters.urgency.includes(',')
      ? (initialFilters.urgency as UrgencyFilter)
      : 'ALL',
  );
  const [urgencyCsv, setUrgencyCsv] = useState<string | null>(
    initialFilters.urgency?.includes(',') ? initialFilters.urgency : null,
  );
  const [departmentFilter, setDepartmentFilter] = useState<DepartmentFilter>(
    initialFilters.departmentId ?? 'ALL',
  );
  const [slaFilter, setSlaFilter] = useState<SlaFilter>(
    (initialFilters.slaState as SlaFilter) ?? 'ALL',
  );
  const [contentSafetyFilter, setContentSafetyFilter] = useState<ContentSafetyFilter>(
    (initialFilters.contentSafetyStatus as ContentSafetyFilter) ?? 'ALL',
  );
  const [openOnly, setOpenOnly] = useState(Boolean(initialFilters.openOnly));
  const [ticketIds, setTicketIds] = useState<string[]>(initialFilters.ticketIds ?? []);
  const [workerId, setWorkerId] = useState(initialFilters.workerId);
  const [teamId, setTeamId] = useState(initialFilters.teamId);
  const [queueView, setQueueView] = useState<QueueViewId>(queueViewFromNavigation(initialFilters));
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(
    initialFilters.focusTicket ?? null,
  );
  const [checkedTicketIds, setCheckedTicketIds] = useState<string[]>([]);
  const [queueEpoch, setQueueEpoch] = useState(0);
  const [previewTicket, setPreviewTicket] = useState<Ticket | null>(null);
  const [previewForId, setPreviewForId] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewRetry, setPreviewRetry] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [canGoPrevious, setCanGoPrevious] = useState(false);
  const [approximateTotal, setApproximateTotal] = useState<number | null>(null);
  const hasLoadedTickets = useRef(false);
  const requestGeneration = useRef(0);
  const cursorHistoryRef = useRef<(string | null)[]>([]);

  function applyNavigationFilters(filters: DashboardNavigationFilters) {
    setStatusFilter((filters.status as StatusFilter) ?? 'ALL');
    setCategoryFilter(filters.category ?? 'ALL');
    setUrgencyFilter(
      filters.urgency && !filters.urgency.includes(',')
        ? (filters.urgency as UrgencyFilter)
        : 'ALL',
    );
    setUrgencyCsv(filters.urgency?.includes(',') ? filters.urgency : null);
    setDepartmentFilter(filters.departmentId ?? 'ALL');
    setSlaFilter((filters.slaState as SlaFilter) ?? 'ALL');
    setContentSafetyFilter((filters.contentSafetyStatus as ContentSafetyFilter) ?? 'ALL');
    setOpenOnly(Boolean(filters.openOnly));
    setTicketIds(filters.ticketIds ?? []);
    setWorkerId(filters.workerId);
    setTeamId(filters.teamId);
    setQueueView(queueViewFromNavigation(filters));
    setSelectedTicketId(filters.focusTicket ?? null);
    setCursor(null);
    cursorHistoryRef.current = [];
    setCanGoPrevious(false);
  }

  const stateFilters = useMemo(
    () => ({
      status: statusFilter !== 'ALL' ? statusFilter : undefined,
      category: categoryFilter !== 'ALL' ? categoryFilter : undefined,
      urgency: urgencyCsv || (urgencyFilter !== 'ALL' ? urgencyFilter : undefined),
      departmentId: departmentFilter !== 'ALL' ? departmentFilter : undefined,
      slaState: slaFilter !== 'ALL' ? slaFilter : undefined,
      contentSafetyStatus: contentSafetyFilter !== 'ALL' ? contentSafetyFilter : undefined,
      assignmentState: queueView === 'unassigned' ? 'unassigned' : undefined,
      openOnly: openOnly || undefined,
      ticketIds: ticketIds.length > 0 ? ticketIds : undefined,
      workerId,
      teamId,
      focusTicket: selectedTicketId ?? undefined,
    }),
    [
      categoryFilter,
      departmentFilter,
      openOnly,
      queueView,
      selectedTicketId,
      slaFilter,
      contentSafetyFilter,
      statusFilter,
      teamId,
      ticketIds,
      urgencyCsv,
      urgencyFilter,
      workerId,
    ],
  );
  useDashboardLocationSync(stateFilters, applyNavigationFilters);

  const debouncedStatus = useDebouncedValue(statusFilter, FILTER_DEBOUNCE_MS);
  const debouncedCategory = useDebouncedValue(categoryFilter, FILTER_DEBOUNCE_MS);
  const debouncedUrgency = useDebouncedValue(urgencyFilter, FILTER_DEBOUNCE_MS);
  const debouncedDepartment = useDebouncedValue(departmentFilter, FILTER_DEBOUNCE_MS);
  const debouncedSla = useDebouncedValue(slaFilter, FILTER_DEBOUNCE_MS);
  const debouncedContentSafety = useDebouncedValue(contentSafetyFilter, FILTER_DEBOUNCE_MS);
  const debouncedSearch = useDebouncedValue(searchQuery, FILTER_DEBOUNCE_MS);
  const debouncedQueueView = useDebouncedValue(queueView, FILTER_DEBOUNCE_MS);

  const serverFilters = useMemo(
    () =>
      buildServerFilters({
        status: debouncedStatus,
        category: debouncedCategory,
        urgency: debouncedUrgency,
        department: debouncedDepartment,
        sla: debouncedSla,
        contentSafetyStatus: debouncedContentSafety,
        queueView: debouncedQueueView,
        search: debouncedSearch,
        urgencyCsv,
        openOnly,
        ticketIds,
        workerId,
        teamId,
      }),
    [
      debouncedCategory,
      debouncedDepartment,
      debouncedQueueView,
      debouncedSearch,
      debouncedSla,
      debouncedContentSafety,
      debouncedStatus,
      debouncedUrgency,
      openOnly,
      teamId,
      ticketIds,
      urgencyCsv,
      workerId,
    ],
  );

  const hasActiveServerFilters =
    (serverFilters.status && serverFilters.status !== 'ALL') ||
    (serverFilters.category && serverFilters.category !== 'ALL') ||
    (serverFilters.urgency && serverFilters.urgency !== 'ALL') ||
    (serverFilters.departmentId && serverFilters.departmentId !== 'ALL') ||
    (serverFilters.slaState && serverFilters.slaState !== 'ALL') ||
    (serverFilters.contentSafetyStatus && serverFilters.contentSafetyStatus !== 'ALL') ||
    (serverFilters.assignmentState && serverFilters.assignmentState !== 'ALL') ||
    Boolean(serverFilters.q) ||
    Boolean(serverFilters.openOnly) ||
    Boolean(serverFilters.ticketIds?.length) ||
    Boolean(serverFilters.workerId) ||
    Boolean(serverFilters.teamId);

  const hasActiveFilters =
    hasActiveServerFilters ||
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    slaFilter !== 'ALL' ||
    contentSafetyFilter !== 'ALL' ||
    searchQuery.trim().length > 0 ||
    queueView !== 'all' ||
    openOnly ||
    ticketIds.length > 0 ||
    Boolean(workerId) ||
    Boolean(teamId) ||
    Boolean(urgencyCsv);

  // Reset to the first page whenever server filters change.
  useEffect(() => {
    setCursor(null);
    cursorHistoryRef.current = [];
    setCanGoPrevious(false);
  }, [serverFilters]);

  useEffect(() => {
    const controller = new AbortController();
    const generation = ++requestGeneration.current;

    async function loadTickets() {
      const isInitialLoad = !hasLoadedTickets.current;
      if (isInitialLoad) {
        setLoadState('loading');
      } else {
        setIsRefreshing(true);
      }
      setErrorMessage(null);

      try {
        const page = await fetchTicketsPage({
          filters: serverFilters,
          cursor,
          signal: controller.signal,
        });
        if (controller.signal.aborted || generation !== requestGeneration.current) {
          return;
        }
        setPageTickets(page.tickets);
        setNextCursor(page.nextCursor);
        setApproximateTotal(page.approximateTotal);
        if (!hasActiveServerFilters && cursor === null) {
          setBaselineTickets(page.tickets);
        }
        hasLoadedTickets.current = true;
        setLoadState('success');

        if (page.revalidate) {
          setIsRefreshing(true);
          void page.revalidate
            .then((fresh) => {
              if (controller.signal.aborted || generation !== requestGeneration.current) {
                return;
              }
              setPageTickets(fresh.tickets);
              setNextCursor(fresh.nextCursor);
              setApproximateTotal(fresh.approximateTotal);
              if (!hasActiveServerFilters && cursor === null) {
                setBaselineTickets(fresh.tickets);
              }
              setIsRefreshing(false);
            })
            .catch(() => {
              if (generation === requestGeneration.current) {
                setIsRefreshing(false);
              }
            });
        } else {
          setIsRefreshing(false);
        }
      } catch (error) {
        if (controller.signal.aborted || generation !== requestGeneration.current) {
          return;
        }
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
        const message = error instanceof Error ? error.message : t('errors.loadTickets');
        if (cursor && /cursor/i.test(message) && /invalid/i.test(message)) {
          cursorHistoryRef.current = [];
          setCanGoPrevious(false);
          setNextCursor(null);
          setCursor(null);
          setIsRefreshing(false);
          return;
        }
        setErrorMessage(message);
        if (isInitialLoad) {
          setLoadState('error');
        }
        setIsRefreshing(false);
      }
    }

    void loadTickets();

    return () => {
      controller.abort();
    };
  }, [cursor, hasActiveServerFilters, queueEpoch, serverFilters, t]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadAggregates() {
      try {
        const data = await fetchTicketAggregates(controller.signal);
        if (!controller.signal.aborted) {
          setAggregates(data);
        }
      } catch {
        // Keep prior aggregates; list remains usable without sidebar totals.
      }
    }

    void loadAggregates();
    return () => controller.abort();
  }, [pageTickets, queueEpoch]);

  const attentionStats = useMemo(() => aggregatesToAttentionStats(aggregates), [aggregates]);
  const categoryOptions = useMemo(
    () => getCategoryFilterOptions(baselineTickets.length > 0 ? baselineTickets : pageTickets, t),
    [baselineTickets, pageTickets, t],
  );
  const highCount = aggregates?.highCount ?? 0;
  const totalCount =
    approximateTotal ??
    aggregates?.openCount ??
    (baselineTickets.length > 0 ? baselineTickets.length : pageTickets.length);

  const previewMatchesSelection = previewForId === selectedTicketId;
  const displayedPreview = previewMatchesSelection ? previewTicket : null;
  const displayedPreviewError = previewMatchesSelection ? previewError : null;

  useEffect(() => {
    if (selectedTicketId && !pageTickets.some((ticket) => ticket.ticketId === selectedTicketId)) {
      setSelectedTicketId(null);
    }
  }, [pageTickets, selectedTicketId]);

  useEffect(() => {
    if (!selectedTicketId) {
      setPreviewTicket(null);
      setPreviewForId(null);
      setPreviewError(null);
      return;
    }

    let cancelled = false;
    setPreviewForId(null);
    setPreviewTicket(null);
    setPreviewError(null);

    void fetchTicketById(selectedTicketId)
      .then((ticket) => {
        if (cancelled) {
          return;
        }
        if (!ticket) {
          setPreviewTicket(null);
          setPreviewError(t('ticket.unableLoad'));
          setPreviewForId(selectedTicketId);
          return;
        }
        setPreviewTicket(ticket);
        setPreviewError(null);
        setPreviewForId(selectedTicketId);
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setPreviewTicket(null);
        setPreviewError(error instanceof Error ? error.message : t('ticket.unableLoad'));
        setPreviewForId(selectedTicketId);
      });

    return () => {
      cancelled = true;
    };
  }, [previewRetry, selectedTicketId, t]);

  function ticketMatchesActiveServerFilters(ticket: Ticket): boolean {
    if (
      serverFilters.status &&
      serverFilters.status !== 'ALL' &&
      ticket.status !== serverFilters.status
    ) {
      return false;
    }
    if (
      serverFilters.category &&
      serverFilters.category !== 'ALL' &&
      ticket.category !== serverFilters.category
    ) {
      return false;
    }
    if (
      serverFilters.urgency &&
      serverFilters.urgency !== 'ALL' &&
      ticket.priority !== serverFilters.urgency
    ) {
      return false;
    }
    if (
      serverFilters.departmentId &&
      serverFilters.departmentId !== 'ALL' &&
      ticket.departmentId !== serverFilters.departmentId
    ) {
      return false;
    }
    if (
      serverFilters.slaState &&
      serverFilters.slaState !== 'ALL' &&
      ticket.sla?.state !== serverFilters.slaState
    ) {
      return false;
    }
    if (serverFilters.assignmentState === 'unassigned' && ticket.departmentId) {
      return false;
    }
    if (serverFilters.assignmentState === 'assigned' && !ticket.departmentId) {
      return false;
    }
    return true;
  }

  function handleTicketUpdated(updated: Ticket) {
    setPreviewTicket((current) => (current?.ticketId === updated.ticketId ? updated : current));

    setBaselineTickets((current) => {
      const exists = current.some((ticket) => ticket.ticketId === updated.ticketId);
      if (!exists) {
        return current;
      }
      return current.map((ticket) => (ticket.ticketId === updated.ticketId ? updated : ticket));
    });

    setPageTickets((current) => {
      const matches = ticketMatchesActiveServerFilters(updated);
      const exists = current.some((ticket) => ticket.ticketId === updated.ticketId);
      if (!matches) {
        return current.filter((ticket) => ticket.ticketId !== updated.ticketId);
      }
      if (exists) {
        return current.map((ticket) => (ticket.ticketId === updated.ticketId ? updated : ticket));
      }
      return current;
    });
  }

  const queueTitle = hasActiveFilters ? t('tickets.matchingReports') : t('tickets.citizenReports');

  function clearFilters() {
    setSearchQuery('');
    setStatusFilter('ALL');
    setCategoryFilter('ALL');
    setUrgencyFilter('ALL');
    setUrgencyCsv(null);
    setDepartmentFilter('ALL');
    setSlaFilter('ALL');
    setContentSafetyFilter('ALL');
    setOpenOnly(false);
    setTicketIds([]);
    setWorkerId(undefined);
    setTeamId(undefined);
    setQueueView('all');
    setCursor(null);
    cursorHistoryRef.current = [];
    setCanGoPrevious(false);
  }

  function handleViewChange(view: QueueViewId) {
    setQueueView(view);
    setCursor(null);
    cursorHistoryRef.current = [];
    setCanGoPrevious(false);
    if (view === 'critical') {
      setUrgencyFilter('critical');
      setSlaFilter('ALL');
      return;
    }
    if (view === 'high') {
      setUrgencyFilter('high');
      setSlaFilter('ALL');
      return;
    }
    if (view === 'aging') {
      setSlaFilter('overdue');
      if (urgencyFilter === 'critical' || urgencyFilter === 'high') {
        setUrgencyFilter('ALL');
      }
      return;
    }
    if (view === 'all' || view === 'unassigned') {
      if (urgencyFilter === 'critical' || urgencyFilter === 'high') {
        setUrgencyFilter('ALL');
      }
      if (slaFilter === 'overdue') {
        setSlaFilter('ALL');
      }
    }
  }

  function goToNextPage() {
    if (!nextCursor) {
      return;
    }
    cursorHistoryRef.current.push(cursor);
    setCanGoPrevious(true);
    setCursor(nextCursor);
  }

  function goToPreviousPage() {
    if (cursorHistoryRef.current.length === 0) {
      return;
    }
    const previous = cursorHistoryRef.current.pop() ?? null;
    setCanGoPrevious(cursorHistoryRef.current.length > 0);
    setCursor(previous);
  }

  return (
    <DashboardLayout title={t('tickets.queueTitle')} subtitle={t('tickets.queueSubtitle')} flush>
      {loadState === 'loading' && (
        <div className="ticket-list-page__loading">
          <LoadingState />
        </div>
      )}

      {loadState === 'error' && (
        <div className="ticket-list-page__error ticket-list-page__error--padded" role="alert">
          <h3>{t('tickets.unableLoad')}</h3>
          <p>{errorMessage}</p>
          <button
            type="button"
            className="ticket-list-page__retry"
            onClick={() => setQueueEpoch((value) => value + 1)}
          >
            {t('common.tryAgain')}
          </button>
        </div>
      )}

      {loadState === 'success' && aggregates && (
        <div className="ticket-list-page__ops-counts" role="status">
          {[
            ['queued', aggregates.queuedCount ?? 0],
            ['assigned', aggregates.assignedCount ?? 0],
            ['inProgress', aggregates.inProgressCount ?? 0],
            ['dueSoon', aggregates.dueSoonCount ?? 0],
            ['workforceUnassigned', aggregates.workforceUnassignedCount ?? 0],
            ['completed', aggregates.completedCount ?? 0],
            ['cancelled', aggregates.cancelledCount ?? 0],
          ].map(([label, count]) => (
            <span className="ticket-list-page__ops-count" key={label}>
              <span>{t(`tickets.opsLabels.${label}`)}</span>
              <strong>{count}</strong>
            </span>
          ))}
        </div>
      )}

      {loadState === 'success' && (
        <div
          className={
            selectedTicketId ? 'helpdesk-desk helpdesk-desk--preview-open' : 'helpdesk-desk'
          }
        >
          <QueueViewsSidebar
            activeView={queueView}
            stats={attentionStats}
            totalCount={totalCount}
            highCount={highCount}
            approximate={aggregates?.approximate ?? false}
            onViewChange={handleViewChange}
          />

          <section className="helpdesk-desk__list" aria-label={t('tickets.queueList')}>
            <TicketFilters
              searchQuery={searchQuery}
              statusFilter={statusFilter}
              categoryFilter={categoryFilter}
              urgencyFilter={urgencyFilter}
              departmentFilter={departmentFilter}
              slaFilter={slaFilter}
              contentSafetyFilter={contentSafetyFilter}
              categoryOptions={categoryOptions}
              resultCount={pageTickets.length}
              totalCount={totalCount}
              isRefreshing={isRefreshing}
              onSearchChange={setSearchQuery}
              onStatusChange={setStatusFilter}
              onCategoryChange={setCategoryFilter}
              onUrgencyChange={(urgency) => {
                setUrgencyFilter(urgency);
                if (urgency === 'critical') {
                  setQueueView('critical');
                } else if (urgency === 'high') {
                  setQueueView('high');
                } else if (queueView === 'critical' || queueView === 'high') {
                  setQueueView('all');
                }
              }}
              onDepartmentChange={setDepartmentFilter}
              onSlaChange={(sla) => {
                setSlaFilter(sla);
                if (sla === 'overdue') {
                  setQueueView('aging');
                } else if (queueView === 'aging') {
                  setQueueView('all');
                }
              }}
              onContentSafetyChange={setContentSafetyFilter}
              onClearFilters={clearFilters}
            />

            {errorMessage && !isRefreshing && (
              <div className="ticket-list-page__error" role="alert">
                <h3>{t('tickets.unableUpdate')}</h3>
                <p>{errorMessage}</p>
              </div>
            )}

            {pageTickets.length === 0 && !hasActiveFilters && <EmptyState />}

            {hasActiveFilters && pageTickets.length === 0 && (
              <EmptyState
                title={
                  ticketIds.length > 0 ? t('tickets.emptyGoneTitle') : t('tickets.emptyMatchTitle')
                }
                message={
                  ticketIds.length > 0 ? t('tickets.emptyGoneBody') : t('tickets.emptyMatchBody')
                }
                visual="search"
              />
            )}

            {pageTickets.length > 0 && (
              <>
                <BulkTicketAssignmentBar
                  selectedTicketIds={checkedTicketIds}
                  ticketNumbers={Object.fromEntries(
                    pageTickets.map((ticket) => [ticket.ticketId, ticket.ticketNumber]),
                  )}
                  onClear={() => setCheckedTicketIds([])}
                  onCommitted={(committed) => {
                    const succeeded = new Set(
                      committed.items.filter((item) => item.ok).map((item) => item.ticketId),
                    );
                    setCheckedTicketIds((current) => current.filter((id) => !succeeded.has(id)));
                    setQueueEpoch((current) => current + 1);
                  }}
                />
                <TicketTable
                  tickets={pageTickets}
                  title={queueTitle}
                  selectedTicketId={selectedTicketId}
                  onSelectTicket={setSelectedTicketId}
                  checkedTicketIds={checkedTicketIds}
                  onToggleChecked={(ticketId) => {
                    setCheckedTicketIds((current) =>
                      current.includes(ticketId)
                        ? current.filter((id) => id !== ticketId)
                        : [...current, ticketId],
                    );
                  }}
                  onToggleAllChecked={() => {
                    const pageIds = pageTickets.map((ticket) => ticket.ticketId);
                    const allChecked = pageIds.every((id) => checkedTicketIds.includes(id));
                    setCheckedTicketIds(
                      allChecked
                        ? checkedTicketIds.filter((id) => !pageIds.includes(id))
                        : [...new Set([...checkedTicketIds, ...pageIds])],
                    );
                  }}
                />
              </>
            )}

            {(nextCursor || canGoPrevious) && (
              <nav className="ticket-list-page__pagination" aria-label={t('tickets.pages')}>
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!canGoPrevious || isRefreshing}
                  onClick={goToPreviousPage}
                >
                  {t('tickets.previous')}
                </button>
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!nextCursor || isRefreshing}
                  onClick={goToNextPage}
                >
                  {t('tickets.next')}
                </button>
              </nav>
            )}

            <details className="ticket-list-page__insights">
              <summary className="ticket-list-page__insights-summary">
                {t('tickets.insights')}
                <span className="ticket-list-page__insights-note">{t('tickets.insightsNote')}</span>
              </summary>
              <div className="ticket-list-page__insights-body">
                <CategoryDistributionChart
                  tickets={baselineTickets.length > 0 ? baselineTickets : pageTickets}
                />
                <DepartmentSummary
                  tickets={baselineTickets.length > 0 ? baselineTickets : pageTickets}
                />
              </div>
            </details>
          </section>

          {selectedTicketId ? (
            <TicketPreviewPanel
              ticket={displayedPreview}
              loadError={displayedPreviewError}
              onRetry={() => {
                setPreviewForId(null);
                setPreviewError(null);
                setPreviewRetry((current) => current + 1);
              }}
              onClose={() => setSelectedTicketId(null)}
              onTicketUpdated={handleTicketUpdated}
            />
          ) : null}
        </div>
      )}
    </DashboardLayout>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import type { TicketAggregates } from '@/types/ticketCollection';
import {
  fetchTicketAggregates,
  fetchTicketsPage,
  type FetchTicketsFilters,
} from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketTable } from '@/components/TicketTable';
import { QueueViewsSidebar, type QueueViewId } from '@/components/QueueViewsSidebar';
import { TicketPreviewPanel } from '@/components/TicketPreviewPanel';
import { CategoryDistributionChart } from '@/components/CategoryDistributionChart';
import { DepartmentSummary } from '@/components/DepartmentSummary';
import { TicketFilters, type SlaFilter } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
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
}): FetchTicketsFilters {
  const filters: FetchTicketsFilters = {
    status: input.status,
    category: input.category,
    urgency: input.urgency,
    departmentId: input.department,
    slaState: input.sla,
    q: input.search.trim() || undefined,
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

export function TicketListPage() {
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [pageTickets, setPageTickets] = useState<Ticket[]>([]);
  const [baselineTickets, setBaselineTickets] = useState<Ticket[]>([]);
  const [aggregates, setAggregates] = useState<TicketAggregates | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL');
  const [urgencyFilter, setUrgencyFilter] = useState<UrgencyFilter>('ALL');
  const [departmentFilter, setDepartmentFilter] = useState<DepartmentFilter>('ALL');
  const [slaFilter, setSlaFilter] = useState<SlaFilter>('ALL');
  const [queueView, setQueueView] = useState<QueueViewId>('all');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [canGoPrevious, setCanGoPrevious] = useState(false);
  const [approximateTotal, setApproximateTotal] = useState<number | null>(null);
  const hasLoadedTickets = useRef(false);
  const requestGeneration = useRef(0);
  const cursorHistoryRef = useRef<(string | null)[]>([]);

  const debouncedStatus = useDebouncedValue(statusFilter, FILTER_DEBOUNCE_MS);
  const debouncedCategory = useDebouncedValue(categoryFilter, FILTER_DEBOUNCE_MS);
  const debouncedUrgency = useDebouncedValue(urgencyFilter, FILTER_DEBOUNCE_MS);
  const debouncedDepartment = useDebouncedValue(departmentFilter, FILTER_DEBOUNCE_MS);
  const debouncedSla = useDebouncedValue(slaFilter, FILTER_DEBOUNCE_MS);
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
        queueView: debouncedQueueView,
        search: debouncedSearch,
      }),
    [
      debouncedCategory,
      debouncedDepartment,
      debouncedQueueView,
      debouncedSearch,
      debouncedSla,
      debouncedStatus,
      debouncedUrgency,
    ],
  );

  const hasActiveServerFilters =
    (serverFilters.status && serverFilters.status !== 'ALL') ||
    (serverFilters.category && serverFilters.category !== 'ALL') ||
    (serverFilters.urgency && serverFilters.urgency !== 'ALL') ||
    (serverFilters.departmentId && serverFilters.departmentId !== 'ALL') ||
    (serverFilters.slaState && serverFilters.slaState !== 'ALL') ||
    (serverFilters.assignmentState && serverFilters.assignmentState !== 'ALL') ||
    Boolean(serverFilters.q) ||
    Boolean(serverFilters.openOnly);

  const hasActiveFilters =
    hasActiveServerFilters ||
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    slaFilter !== 'ALL' ||
    searchQuery.trim().length > 0 ||
    queueView !== 'all';

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
        setErrorMessage(error instanceof Error ? error.message : 'Unable to load tickets.');
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
  }, [cursor, hasActiveServerFilters, serverFilters]);

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
  }, [pageTickets]);

  const attentionStats = useMemo(() => aggregatesToAttentionStats(aggregates), [aggregates]);
  const categoryOptions = useMemo(
    () => getCategoryFilterOptions(baselineTickets.length > 0 ? baselineTickets : pageTickets),
    [baselineTickets, pageTickets],
  );
  const highCount = aggregates?.highCount ?? 0;
  const totalCount =
    aggregates?.openCount ??
    approximateTotal ??
    (baselineTickets.length > 0 ? baselineTickets.length : pageTickets.length);

  const selectedTicket = useMemo(() => {
    if (!selectedTicketId) {
      return null;
    }
    return (
      pageTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      baselineTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      null
    );
  }, [baselineTickets, selectedTicketId, pageTickets]);

  useEffect(() => {
    if (selectedTicketId && !pageTickets.some((ticket) => ticket.ticketId === selectedTicketId)) {
      setSelectedTicketId(null);
    }
  }, [pageTickets, selectedTicketId]);

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

  const queueTitle = hasActiveFilters ? 'Matching reports' : 'Citizen reports';

  function clearFilters() {
    setSearchQuery('');
    setStatusFilter('ALL');
    setCategoryFilter('ALL');
    setUrgencyFilter('ALL');
    setDepartmentFilter('ALL');
    setSlaFilter('ALL');
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
    <DashboardLayout
      title="Work queue"
      subtitle="Triage citizen infrastructure reports by urgency, ownership, and age"
      flush
      search={{
        value: searchQuery,
        onChange: setSearchQuery,
        label: 'Search tickets',
        placeholder: 'Search ticket #, location, or description…',
      }}
    >
      {loadState === 'loading' && (
        <div className="ticket-list-page__loading">
          <LoadingState />
        </div>
      )}

      {loadState === 'error' && (
        <div className="ticket-list-page__error ticket-list-page__error--padded" role="alert">
          <h3>Unable to load tickets</h3>
          <p>{errorMessage}</p>
        </div>
      )}

      {loadState === 'success' && (
        <div className="helpdesk-desk">
          <QueueViewsSidebar
            activeView={queueView}
            stats={attentionStats}
            totalCount={totalCount}
            highCount={highCount}
            approximate={aggregates?.approximate ?? false}
            onViewChange={handleViewChange}
          />

          <section className="helpdesk-desk__list" aria-label="Work queue list">
            <TicketFilters
              searchQuery={searchQuery}
              statusFilter={statusFilter}
              categoryFilter={categoryFilter}
              urgencyFilter={urgencyFilter}
              departmentFilter={departmentFilter}
              slaFilter={slaFilter}
              categoryOptions={categoryOptions}
              resultCount={pageTickets.length}
              totalCount={totalCount}
              isRefreshing={isRefreshing}
              hideSearch
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
              onClearFilters={clearFilters}
            />

            {errorMessage && !isRefreshing && (
              <div className="ticket-list-page__error" role="alert">
                <h3>Unable to update tickets</h3>
                <p>{errorMessage}</p>
              </div>
            )}

            {pageTickets.length === 0 && !hasActiveFilters && <EmptyState />}

            {hasActiveFilters && pageTickets.length === 0 && (
              <EmptyState
                title="No matching tickets"
                message="Try adjusting your search, status, category, urgency, or department filters to find tickets."
              />
            )}

            {pageTickets.length > 0 && (
              <TicketTable
                tickets={pageTickets}
                title={queueTitle}
                selectedTicketId={selectedTicket?.ticketId ?? null}
                onSelectTicket={setSelectedTicketId}
              />
            )}

            {(nextCursor || canGoPrevious) && (
              <nav className="ticket-list-page__pagination" aria-label="Ticket pages">
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!canGoPrevious || isRefreshing}
                  onClick={goToPreviousPage}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!nextCursor || isRefreshing}
                  onClick={goToNextPage}
                >
                  Next
                </button>
              </nav>
            )}

            <details className="ticket-list-page__insights">
              <summary className="ticket-list-page__insights-summary">
                Operational insights
                <span className="ticket-list-page__insights-note">
                  Secondary — category & workload
                </span>
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

          <TicketPreviewPanel ticket={selectedTicket} onTicketUpdated={handleTicketUpdated} />
        </div>
      )}
    </DashboardLayout>
  );
}

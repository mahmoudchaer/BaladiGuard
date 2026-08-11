import { useEffect, useMemo, useRef, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import type { TicketAggregates } from '@/types/ticketCollection';
import { fetchTicketAggregates, fetchTicketsPage } from '@/services/tickets';
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
  filterTickets,
  getCategoryFilterOptions,
  type CategoryFilter,
  type DepartmentFilter,
  type QueueAttentionStats,
  type StatusFilter,
  type UrgencyFilter,
} from '@/utils/ticketStats';
import './TicketListPage.css';

type LoadState = 'loading' | 'success' | 'error';

const OPEN_STATUSES = new Set(['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS']);
const AGING_MS = 3 * 24 * 60 * 60 * 1000;
const FILTER_DEBOUNCE_MS = import.meta.env.MODE === 'test' ? 0 : 300;

function isOpenTicket(ticket: Ticket): boolean {
  return OPEN_STATUSES.has(ticket.status);
}

function applyQueueView(tickets: Ticket[], view: QueueViewId, now = Date.now()): Ticket[] {
  switch (view) {
    case 'critical':
      return tickets.filter((ticket) => isOpenTicket(ticket) && ticket.priority === 'critical');
    case 'high':
      return tickets.filter((ticket) => isOpenTicket(ticket) && ticket.priority === 'high');
    case 'unassigned':
      return tickets.filter((ticket) => isOpenTicket(ticket) && !ticket.departmentId);
    case 'aging':
      return tickets.filter((ticket) => {
        if (!isOpenTicket(ticket)) {
          return false;
        }
        const createdAt = Date.parse(ticket.createdAt);
        return Number.isFinite(createdAt) && now - createdAt >= AGING_MS;
      });
    default:
      return tickets;
  }
}

function aggregatesToAttentionStats(aggregates: TicketAggregates | null): QueueAttentionStats {
  return {
    critical: aggregates?.criticalCount ?? 0,
    unassigned: aggregates?.unassignedCount ?? 0,
    aging: aggregates?.overdueCount ?? 0,
  };
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
  const [previousCursor, setPreviousCursor] = useState<string | null>(null);
  const [approximateTotal, setApproximateTotal] = useState<number | null>(null);
  const hasLoadedTickets = useRef(false);
  const requestGeneration = useRef(0);

  const debouncedStatus = useDebouncedValue(statusFilter, FILTER_DEBOUNCE_MS);
  const debouncedCategory = useDebouncedValue(categoryFilter, FILTER_DEBOUNCE_MS);
  const debouncedUrgency = useDebouncedValue(urgencyFilter, FILTER_DEBOUNCE_MS);
  const debouncedDepartment = useDebouncedValue(departmentFilter, FILTER_DEBOUNCE_MS);
  const debouncedSla = useDebouncedValue(slaFilter, FILTER_DEBOUNCE_MS);
  const debouncedSearch = useDebouncedValue(searchQuery, FILTER_DEBOUNCE_MS);

  const hasActiveServerFilters =
    debouncedStatus !== 'ALL' ||
    debouncedCategory !== 'ALL' ||
    debouncedUrgency !== 'ALL' ||
    debouncedDepartment !== 'ALL' ||
    debouncedSla !== 'ALL';
  const hasActiveFilters =
    hasActiveServerFilters ||
    debouncedSearch.trim().length > 0 ||
    queueView !== 'all' ||
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    slaFilter !== 'ALL' ||
    searchQuery.trim().length > 0;

  // Reset to the first page whenever server filters change.
  useEffect(() => {
    setCursor(null);
  }, [debouncedStatus, debouncedCategory, debouncedUrgency, debouncedDepartment, debouncedSla]);

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
          filters: {
            status: debouncedStatus,
            category: debouncedCategory,
            urgency: debouncedUrgency,
            departmentId: debouncedDepartment,
            slaState: debouncedSla,
          },
          cursor,
          signal: controller.signal,
        });
        if (controller.signal.aborted || generation !== requestGeneration.current) {
          return;
        }
        setPageTickets(page.tickets);
        setNextCursor(page.nextCursor);
        setPreviousCursor(page.previousCursor);
        setApproximateTotal(page.approximateTotal);
        if (!hasActiveServerFilters && cursor === null) {
          setBaselineTickets(page.tickets);
        }
        hasLoadedTickets.current = true;
        setLoadState('success');
        setIsRefreshing(false);
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
  }, [
    cursor,
    debouncedCategory,
    debouncedDepartment,
    debouncedSla,
    debouncedStatus,
    debouncedUrgency,
    hasActiveServerFilters,
  ]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadAggregates() {
      try {
        const data = await fetchTicketAggregates(controller.signal);
        if (!controller.signal.aborted) {
          setAggregates(data);
        }
      } catch {
        if (!controller.signal.aborted) {
          // Keep prior aggregates; list remains usable without sidebar totals.
        }
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

  const filteredTickets = useMemo(() => {
    const searched = filterTickets(pageTickets, debouncedSearch, 'ALL', 'ALL', 'ALL', 'ALL');
    return applyQueueView(searched, queueView);
  }, [pageTickets, debouncedSearch, queueView]);

  const selectedTicket = useMemo(() => {
    if (!selectedTicketId) {
      return null;
    }
    return (
      filteredTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      pageTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      baselineTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      null
    );
  }, [baselineTickets, filteredTickets, selectedTicketId, pageTickets]);

  useEffect(() => {
    if (
      selectedTicketId &&
      !filteredTickets.some((ticket) => ticket.ticketId === selectedTicketId)
    ) {
      setSelectedTicketId(null);
    }
  }, [filteredTickets, selectedTicketId]);

  function ticketMatchesActiveServerFilters(ticket: Ticket): boolean {
    if (statusFilter !== 'ALL' && ticket.status !== statusFilter) {
      return false;
    }
    if (categoryFilter !== 'ALL' && ticket.category !== categoryFilter) {
      return false;
    }
    if (urgencyFilter !== 'ALL' && ticket.priority !== urgencyFilter) {
      return false;
    }
    if (departmentFilter !== 'ALL' && ticket.departmentId !== departmentFilter) {
      return false;
    }
    if (slaFilter !== 'ALL' && ticket.sla?.state !== slaFilter) return false;
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
  }

  function handleViewChange(view: QueueViewId) {
    setQueueView(view);
    setCursor(null);
    if (view === 'critical') {
      setUrgencyFilter('critical');
      return;
    }
    if (view === 'high') {
      setUrgencyFilter('high');
      return;
    }
    if (view === 'all' || view === 'unassigned' || view === 'aging') {
      if (urgencyFilter === 'critical' || urgencyFilter === 'high') {
        setUrgencyFilter('ALL');
      }
    }
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
              resultCount={filteredTickets.length}
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
              onSlaChange={setSlaFilter}
              onClearFilters={clearFilters}
            />

            {errorMessage && !isRefreshing && (
              <div className="ticket-list-page__error" role="alert">
                <h3>Unable to update tickets</h3>
                <p>{errorMessage}</p>
              </div>
            )}

            {pageTickets.length === 0 && !hasActiveFilters && <EmptyState />}

            {hasActiveFilters && filteredTickets.length === 0 && (
              <EmptyState
                title="No matching tickets"
                message="Try adjusting your search, status, category, urgency, or department filters to find tickets."
              />
            )}

            {filteredTickets.length > 0 && (
              <TicketTable
                tickets={filteredTickets}
                title={queueTitle}
                selectedTicketId={selectedTicket?.ticketId ?? null}
                onSelectTicket={setSelectedTicketId}
              />
            )}

            {(nextCursor || previousCursor) && (
              <nav className="ticket-list-page__pagination" aria-label="Ticket pages">
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!previousCursor || isRefreshing}
                  onClick={() => setCursor(previousCursor)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="ticket-list-page__page-btn"
                  disabled={!nextCursor || isRefreshing}
                  onClick={() => setCursor(nextCursor)}
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

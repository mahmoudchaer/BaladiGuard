import { useEffect, useMemo, useRef, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import { fetchTickets } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketTable } from '@/components/TicketTable';
import { QueueViewsSidebar, type QueueViewId } from '@/components/QueueViewsSidebar';
import { TicketPreviewPanel } from '@/components/TicketPreviewPanel';
import { CategoryDistributionChart } from '@/components/CategoryDistributionChart';
import { DepartmentSummary } from '@/components/DepartmentSummary';
import { TicketFilters } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import {
  computeQueueAttentionStats,
  filterTickets,
  getCategoryFilterOptions,
  type CategoryFilter,
  type DepartmentFilter,
  type StatusFilter,
  type UrgencyFilter,
} from '@/utils/ticketStats';
import './TicketListPage.css';

type LoadState = 'loading' | 'success' | 'error';

const OPEN_STATUSES = new Set(['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS']);
const AGING_MS = 3 * 24 * 60 * 60 * 1000;

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

export function TicketListPage() {
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [allTickets, setAllTickets] = useState<Ticket[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL');
  const [urgencyFilter, setUrgencyFilter] = useState<UrgencyFilter>('ALL');
  const [departmentFilter, setDepartmentFilter] = useState<DepartmentFilter>('ALL');
  const [queueView, setQueueView] = useState<QueueViewId>('all');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const hasLoadedTickets = useRef(false);

  const hasActiveServerFilters =
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL';
  const hasActiveFilters =
    hasActiveServerFilters || searchQuery.trim().length > 0 || queueView !== 'all';

  useEffect(() => {
    let cancelled = false;

    async function loadTickets() {
      const isInitialLoad = !hasLoadedTickets.current;
      if (isInitialLoad) {
        setLoadState('loading');
      } else {
        setIsRefreshing(true);
      }
      setErrorMessage(null);

      try {
        const data = await fetchTickets({
          status: statusFilter,
          category: categoryFilter,
          urgency: urgencyFilter,
          departmentId: departmentFilter,
        });
        if (!cancelled) {
          setTickets(data);
          if (!hasActiveServerFilters) {
            setAllTickets(data);
          }
          hasLoadedTickets.current = true;
          setLoadState('success');
          setIsRefreshing(false);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load tickets.');
          if (isInitialLoad) {
            setLoadState('error');
          }
          setIsRefreshing(false);
        }
      }
    }

    void loadTickets();

    return () => {
      cancelled = true;
    };
  }, [categoryFilter, departmentFilter, hasActiveServerFilters, statusFilter, urgencyFilter]);

  const attentionStats = useMemo(() => computeQueueAttentionStats(allTickets), [allTickets]);
  const categoryOptions = useMemo(() => getCategoryFilterOptions(allTickets), [allTickets]);
  const highCount = useMemo(
    () => allTickets.filter((ticket) => isOpenTicket(ticket) && ticket.priority === 'high').length,
    [allTickets],
  );

  const filteredTickets = useMemo(() => {
    const searched = filterTickets(tickets, searchQuery, 'ALL', 'ALL', 'ALL', 'ALL');
    return applyQueueView(searched, queueView);
  }, [tickets, searchQuery, queueView]);

  const selectedTicket = useMemo(() => {
    if (!selectedTicketId) {
      return null;
    }
    return (
      filteredTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      tickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      allTickets.find((ticket) => ticket.ticketId === selectedTicketId) ??
      null
    );
  }, [allTickets, filteredTickets, selectedTicketId, tickets]);

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
    return true;
  }

  function handleTicketUpdated(updated: Ticket) {
    // Keep the unfiltered cache current for attention stats / category options.
    setAllTickets((current) => {
      const exists = current.some((ticket) => ticket.ticketId === updated.ticketId);
      if (!exists) {
        return current;
      }
      return current.map((ticket) => (ticket.ticketId === updated.ticketId ? updated : ticket));
    });

    // Drop or replace in the active server-filtered list so preview actions do not
    // leave stale rows under the wrong status/category/urgency/department view.
    setTickets((current) => {
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
    setQueueView('all');
  }

  function handleViewChange(view: QueueViewId) {
    setQueueView(view);
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
            totalCount={allTickets.length}
            highCount={highCount}
            onViewChange={handleViewChange}
          />

          <section className="helpdesk-desk__list" aria-label="Work queue list">
            <TicketFilters
              searchQuery={searchQuery}
              statusFilter={statusFilter}
              categoryFilter={categoryFilter}
              urgencyFilter={urgencyFilter}
              departmentFilter={departmentFilter}
              categoryOptions={categoryOptions}
              resultCount={filteredTickets.length}
              totalCount={allTickets.length}
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
              onClearFilters={clearFilters}
            />

            {errorMessage && !isRefreshing && (
              <div className="ticket-list-page__error" role="alert">
                <h3>Unable to update tickets</h3>
                <p>{errorMessage}</p>
              </div>
            )}

            {allTickets.length === 0 && !hasActiveFilters && <EmptyState />}

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

            <details className="ticket-list-page__insights">
              <summary className="ticket-list-page__insights-summary">
                Operational insights
                <span className="ticket-list-page__insights-note">
                  Secondary — category & workload
                </span>
              </summary>
              <div className="ticket-list-page__insights-body">
                <CategoryDistributionChart tickets={allTickets} />
                <DepartmentSummary tickets={allTickets} />
              </div>
            </details>
          </section>

          <TicketPreviewPanel ticket={selectedTicket} onTicketUpdated={handleTicketUpdated} />
        </div>
      )}
    </DashboardLayout>
  );
}

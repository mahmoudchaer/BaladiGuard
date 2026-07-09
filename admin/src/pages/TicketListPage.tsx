import { useEffect, useMemo, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import { fetchTickets } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketTable } from '@/components/TicketTable';
import { StatsCards } from '@/components/StatsCards';
import { TicketFilters } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import {
  computeTicketStats,
  filterTickets,
  getCategoryFilterOptions,
  type CategoryFilter,
  type StatusFilter,
} from '@/utils/ticketStats';

type LoadState = 'loading' | 'success' | 'error';

export function TicketListPage() {
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL');

  useEffect(() => {
    let cancelled = false;

    async function loadTickets() {
      setLoadState('loading');
      setErrorMessage(null);

      try {
        const data = await fetchTickets();
        if (!cancelled) {
          setTickets(data);
          setLoadState('success');
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(error instanceof Error ? error.message : 'Unable to load tickets.');
          setLoadState('error');
        }
      }
    }

    void loadTickets();

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => computeTicketStats(tickets), [tickets]);
  const categoryOptions = useMemo(() => getCategoryFilterOptions(tickets), [tickets]);

  const filteredTickets = useMemo(
    () => filterTickets(tickets, searchQuery, statusFilter, categoryFilter),
    [tickets, searchQuery, statusFilter, categoryFilter],
  );

  return (
    <DashboardLayout>
      {loadState === 'loading' && <LoadingState />}

      {loadState === 'error' && (
        <div className="ticket-list-page__error" role="alert">
          <h3>Unable to load tickets</h3>
          <p>{errorMessage}</p>
        </div>
      )}

      {loadState === 'success' && (
        <>
          <StatsCards stats={stats} />

          <TicketFilters
            searchQuery={searchQuery}
            statusFilter={statusFilter}
            categoryFilter={categoryFilter}
            categoryOptions={categoryOptions}
            resultCount={filteredTickets.length}
            totalCount={tickets.length}
            onSearchChange={setSearchQuery}
            onStatusChange={setStatusFilter}
            onCategoryChange={setCategoryFilter}
          />

          {tickets.length === 0 && <EmptyState />}

          {tickets.length > 0 && filteredTickets.length === 0 && (
            <EmptyState
              title="No matching tickets"
              message="Try adjusting your search, status filter, or category filter to find tickets."
            />
          )}

          {filteredTickets.length > 0 && <TicketTable tickets={filteredTickets} />}
        </>
      )}
    </DashboardLayout>
  );
}

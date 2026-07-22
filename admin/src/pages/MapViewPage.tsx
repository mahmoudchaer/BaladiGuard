import { useEffect, useMemo, useState } from 'react';
import type { Ticket } from '@/types/ticket';
import { fetchTickets } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketMap } from '@/components/TicketMap';
import { TicketFilters } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import {
  filterTickets,
  getCategoryFilterOptions,
  type CategoryFilter,
  type StatusFilter,
} from '@/utils/ticketStats';
import { getPlottableTickets } from '@/utils/ticketLocation';
import './MapViewPage.css';

type LoadState = 'loading' | 'success' | 'error';

export function MapViewPage() {
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

  const categoryOptions = useMemo(() => getCategoryFilterOptions(tickets), [tickets]);

  const filteredTickets = useMemo(
    () => filterTickets(tickets, searchQuery, statusFilter, categoryFilter),
    [tickets, searchQuery, statusFilter, categoryFilter],
  );

  const plottableTickets = useMemo(() => getPlottableTickets(filteredTickets), [filteredTickets]);
  const skippedCount = filteredTickets.length - plottableTickets.length;

  const pinSummary =
    skippedCount > 0
      ? `${plottableTickets.length} pins · ${skippedCount} without coordinates`
      : `${plottableTickets.length} pins`;

  return (
    <DashboardLayout
      title="Map View"
      subtitle="See where citizen infrastructure reports are located"
    >
      {loadState === 'loading' && <LoadingState />}

      {loadState === 'error' && (
        <div className="map-view-page__error" role="alert">
          <h3>Unable to load tickets</h3>
          <p>{errorMessage}</p>
        </div>
      )}

      {loadState === 'success' && (
        <>
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

          {filteredTickets.length > 0 && plottableTickets.length === 0 && (
            <EmptyState
              title="No tickets with valid coordinates"
              message="Matching tickets do not have plottable latitude and longitude values."
            />
          )}

          {plottableTickets.length > 0 && (
            <div className="map-view-page__map-section">
              <p className="map-view-page__pin-summary" aria-live="polite">
                {pinSummary}
              </p>
              <TicketMap tickets={plottableTickets} />
            </div>
          )}
        </>
      )}
    </DashboardLayout>
  );
}

import { useEffect, useMemo, useRef, useState } from 'react';
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
  type DepartmentFilter,
  type StatusFilter,
  type UrgencyFilter,
} from '@/utils/ticketStats';
import { getPlottableTickets } from '@/utils/ticketLocation';
import './MapViewPage.css';

type LoadState = 'loading' | 'success' | 'error';

export function MapViewPage() {
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
  const hasLoadedTickets = useRef(false);

  const hasActiveServerFilters =
    statusFilter !== 'ALL' ||
    categoryFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL';
  const hasActiveFilters = hasActiveServerFilters || searchQuery.trim().length > 0;

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

  const categoryOptions = useMemo(() => getCategoryFilterOptions(allTickets), [allTickets]);

  const filteredTickets = useMemo(
    () => filterTickets(tickets, searchQuery, 'ALL', 'ALL', 'ALL', 'ALL'),
    [tickets, searchQuery],
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
            urgencyFilter={urgencyFilter}
            departmentFilter={departmentFilter}
            categoryOptions={categoryOptions}
            resultCount={filteredTickets.length}
            totalCount={allTickets.length}
            isRefreshing={isRefreshing}
            onSearchChange={setSearchQuery}
            onStatusChange={setStatusFilter}
            onCategoryChange={setCategoryFilter}
            onUrgencyChange={setUrgencyFilter}
            onDepartmentChange={setDepartmentFilter}
            onClearFilters={() => {
              setSearchQuery('');
              setStatusFilter('ALL');
              setCategoryFilter('ALL');
              setUrgencyFilter('ALL');
              setDepartmentFilter('ALL');
            }}
          />

          {errorMessage && !isRefreshing && (
            <div className="map-view-page__error" role="alert">
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

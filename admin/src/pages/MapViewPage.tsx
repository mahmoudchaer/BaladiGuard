import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { TicketMapMarker, TicketMapViewport } from '@/types/ticketCollection';
import { fetchTicketMapViewport } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketMap } from '@/components/TicketMap';
import { TicketFilters } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import {
  getCategoryFilterOptions,
  type CategoryFilter,
  type DepartmentFilter,
  type StatusFilter,
  type UrgencyFilter,
} from '@/utils/ticketStats';
import { BEIRUT_CENTER } from '@/utils/ticketLocation';
import {
  hasMapBounds,
  parseDashboardSearchParams,
  serializeDashboardSearchParams,
} from '@/utils/dashboardNavigation';
import { formatCategory, formatPriority, formatStatus } from '@/utils/labels';
import './MapViewPage.css';

type LoadState = 'loading' | 'success' | 'error';

type MapBounds = {
  north: number;
  south: number;
  east: number;
  west: number;
  zoom: number;
};

const DEFAULT_BOUNDS: MapBounds = {
  north: BEIRUT_CENTER.latitude + 0.08,
  south: BEIRUT_CENTER.latitude - 0.08,
  east: BEIRUT_CENTER.longitude + 0.1,
  west: BEIRUT_CENTER.longitude - 0.1,
  zoom: 12,
};

const FILTER_DEBOUNCE_MS = import.meta.env.MODE === 'test' ? 0 : 300;
const VIEWPORT_DEBOUNCE_MS = import.meta.env.MODE === 'test' ? 0 : 350;

export function MapViewPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigationFilters = useMemo(() => parseDashboardSearchParams(searchParams), [searchParams]);
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [viewport, setViewport] = useState<TicketMapViewport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    (navigationFilters.status as StatusFilter) ?? 'ALL',
  );
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>(
    navigationFilters.category ?? 'ALL',
  );
  const [urgencyFilter, setUrgencyFilter] = useState<UrgencyFilter>(
    navigationFilters.urgency && !navigationFilters.urgency.includes(',')
      ? (navigationFilters.urgency as UrgencyFilter)
      : 'ALL',
  );
  const [urgencyCsv, setUrgencyCsv] = useState<string | null>(
    navigationFilters.urgency?.includes(',') ? navigationFilters.urgency : null,
  );
  const [departmentFilter, setDepartmentFilter] = useState<DepartmentFilter>(
    navigationFilters.departmentId ?? 'ALL',
  );
  const [openOnly, setOpenOnly] = useState(Boolean(navigationFilters.openOnly));
  const [ticketIds, setTicketIds] = useState<string[]>(navigationFilters.ticketIds ?? []);
  const persistBounds = hasMapBounds(navigationFilters);
  const [bounds, setBounds] = useState<MapBounds>(() =>
    persistBounds
      ? {
          north: navigationFilters.north as number,
          south: navigationFilters.south as number,
          east: navigationFilters.east as number,
          west: navigationFilters.west as number,
          zoom: navigationFilters.zoom ?? 15,
        }
      : DEFAULT_BOUNDS,
  );
  const hasLoaded = useRef(false);
  const requestGeneration = useRef(0);

  const debouncedStatus = useDebouncedValue(statusFilter, FILTER_DEBOUNCE_MS);
  const debouncedCategory = useDebouncedValue(categoryFilter, FILTER_DEBOUNCE_MS);
  const debouncedUrgency = useDebouncedValue(urgencyFilter, FILTER_DEBOUNCE_MS);
  const debouncedDepartment = useDebouncedValue(departmentFilter, FILTER_DEBOUNCE_MS);
  const debouncedSearch = useDebouncedValue(searchQuery, FILTER_DEBOUNCE_MS);
  const debouncedBounds = useDebouncedValue(bounds, VIEWPORT_DEBOUNCE_MS);

  const mapUrgency = urgencyCsv || (debouncedUrgency !== 'ALL' ? debouncedUrgency : undefined);
  const hasActiveServerFilters =
    debouncedStatus !== 'ALL' ||
    debouncedCategory !== 'ALL' ||
    Boolean(mapUrgency) ||
    debouncedDepartment !== 'ALL' ||
    openOnly ||
    ticketIds.length > 0;
  const hasActiveFilters = hasActiveServerFilters || debouncedSearch.trim().length > 0;

  useEffect(() => {
    const controller = new AbortController();
    const generation = ++requestGeneration.current;

    async function loadViewport() {
      const isInitialLoad = !hasLoaded.current;
      if (isInitialLoad) {
        setLoadState('loading');
      } else {
        setIsRefreshing(true);
      }
      setErrorMessage(null);

      try {
        const data = await fetchTicketMapViewport({
          ...debouncedBounds,
          filters: {
            status: debouncedStatus,
            category: debouncedCategory,
            urgency: mapUrgency,
            departmentId: debouncedDepartment,
            openOnly: openOnly || undefined,
            ticketIds: ticketIds.length > 0 ? ticketIds : undefined,
          },
          signal: controller.signal,
        });
        if (controller.signal.aborted || generation !== requestGeneration.current) {
          return;
        }
        setViewport(data);
        hasLoaded.current = true;
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

    void loadViewport();
    return () => controller.abort();
  }, [
    debouncedBounds,
    debouncedCategory,
    debouncedDepartment,
    debouncedStatus,
    mapUrgency,
    openOnly,
    ticketIds,
  ]);

  useEffect(() => {
    const next = serializeDashboardSearchParams({
      status: statusFilter !== 'ALL' ? statusFilter : undefined,
      category: categoryFilter !== 'ALL' ? categoryFilter : undefined,
      urgency: urgencyCsv || (urgencyFilter !== 'ALL' ? urgencyFilter : undefined),
      departmentId: departmentFilter !== 'ALL' ? departmentFilter : undefined,
      openOnly: openOnly || undefined,
      ticketIds: ticketIds.length > 0 ? ticketIds : undefined,
      south: persistBounds ? bounds.south : undefined,
      west: persistBounds ? bounds.west : undefined,
      north: persistBounds ? bounds.north : undefined,
      east: persistBounds ? bounds.east : undefined,
      zoom: persistBounds ? bounds.zoom : undefined,
    });
    const ownedCurrent = serializeDashboardSearchParams(
      parseDashboardSearchParams(searchParams),
    ).toString();
    if (!next.toString() || ownedCurrent === next.toString()) {
      return;
    }
    setSearchParams(next, { replace: true });
  }, [
    bounds,
    categoryFilter,
    departmentFilter,
    openOnly,
    searchParams,
    setSearchParams,
    statusFilter,
    ticketIds,
    persistBounds,
    urgencyCsv,
    urgencyFilter,
  ]);

  const handleViewportChange = useCallback((next: MapBounds) => {
    setBounds(next);
  }, []);

  const markers = useMemo(() => {
    const all = viewport?.markers ?? [];
    const query = debouncedSearch.trim().toLowerCase();
    if (!query) {
      return all;
    }
    return all.filter((marker) => {
      const haystack =
        `${marker.ticketNumber ?? ''} ${marker.ticketId} ${marker.category}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [debouncedSearch, viewport?.markers]);

  const clusters = useMemo(() => viewport?.clusters ?? [], [viewport?.clusters]);
  const categoryOptions = useMemo(
    () =>
      getCategoryFilterOptions(
        markers.map((marker) => ({
          ticketId: marker.ticketId,
          ticketNumber: marker.ticketNumber ?? marker.ticketId,
          trackingCode: '',
          description: '',
          contact: {},
          location: {
            latitude: marker.latitude,
            longitude: marker.longitude,
            addressText: '',
            source: 'GPS' as const,
          },
          imageObjectKey: 'unavailable',
          status: marker.status,
          category: marker.category,
          priority: marker.priority,
          createdBy: null,
          municipalityId: null,
          departmentId: null,
          duplicateGroupId: null,
          createdAt: new Date().toISOString(),
          updatedAt: null,
        })),
      ),
    [markers],
  );

  const pinSummary = useMemo(() => {
    if (clusters.length > 0 && markers.length === 0) {
      const total = clusters.reduce((sum, cluster) => sum + cluster.count, 0);
      return `${clusters.length} clusters · ~${total} reports`;
    }
    const truncatedNote = viewport?.truncated ? ' · truncated' : '';
    return `${markers.length} pins${truncatedNote}`;
  }, [clusters, markers.length, viewport?.truncated]);

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
            resultCount={markers.length + clusters.length}
            totalCount={markers.length + clusters.reduce((sum, c) => sum + c.count, 0)}
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
              setUrgencyCsv(null);
              setDepartmentFilter('ALL');
              setOpenOnly(false);
              setTicketIds([]);
            }}
          />

          {errorMessage && !isRefreshing && (
            <div className="map-view-page__error" role="alert">
              <h3>Unable to update tickets</h3>
              <p>{errorMessage}</p>
            </div>
          )}

          {markers.length === 0 && clusters.length === 0 && !hasActiveFilters && (
            <EmptyState
              title="No reports in this area"
              message="Pan or zoom the map, or clear filters, to find citizen reports."
            />
          )}

          {hasActiveFilters && markers.length === 0 && clusters.length === 0 && (
            <EmptyState
              title={
                ticketIds.length > 0
                  ? 'These tickets are no longer available'
                  : 'No matching tickets'
              }
              message={
                ticketIds.length > 0
                  ? 'The referenced tickets are outside this view, were removed, or you no longer have access.'
                  : 'Try adjusting your search, status, category, urgency, or department filters to find tickets.'
              }
            />
          )}

          <div className="map-view-page__map-section">
            <p className="map-view-page__pin-summary" aria-live="polite">
              {pinSummary}
            </p>
            <TicketMap
              markers={markers}
              clusters={clusters}
              truncated={viewport?.truncated}
              initialBounds={
                hasMapBounds(navigationFilters)
                  ? {
                      north: navigationFilters.north as number,
                      south: navigationFilters.south as number,
                      east: navigationFilters.east as number,
                      west: navigationFilters.west as number,
                    }
                  : null
              }
              onViewportChange={handleViewportChange}
            />
          </div>

          <section className="map-view-page__list" aria-label="Accessible ticket list for map">
            <h2 className="map-view-page__list-title">Tickets in view</h2>
            {markers.length === 0 ? (
              <p className="map-view-page__list-empty">
                {clusters.length > 0
                  ? 'Zoom into a cluster to list individual tickets.'
                  : 'No individual tickets in the current viewport.'}
              </p>
            ) : (
              <ul className="map-view-page__list-items">
                {markers.map((marker) => (
                  <MapListItem key={marker.ticketId} marker={marker} />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </DashboardLayout>
  );
}

function MapListItem({ marker }: { marker: TicketMapMarker }) {
  const label = marker.ticketNumber ?? marker.ticketId;
  return (
    <li className="map-view-page__list-item">
      <Link to={`/tickets/${marker.ticketId}`} className="map-view-page__list-link">
        <span className="map-view-page__list-id">{label}</span>
        <span className="map-view-page__list-meta">
          {formatCategory(marker.category)} · {formatStatus(marker.status)}
          {marker.priority ? ` · ${formatPriority(marker.priority)}` : ''}
        </span>
      </Link>
    </li>
  );
}

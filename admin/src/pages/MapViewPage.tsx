import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { TicketMapMarker, TicketMapViewport } from '@/types/ticketCollection';
import { fetchTicketMapViewport } from '@/services/tickets';
import { DashboardLayout } from '@/components/DashboardLayout';
import { TicketMap } from '@/components/TicketMap';
import { TicketFilters } from '@/components/TicketFilters';
import { EmptyState } from '@/components/EmptyState';
import { LoadingState } from '@/components/LoadingState';
import { useI18n } from '@/i18n/LocaleProvider';
import { useDashboardLocationSync } from '@/hooks/useDashboardLocationSync';
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
  type DashboardNavigationFilters,
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
  const { t } = useI18n();
  const initialFilters = parseDashboardSearchParams(new URLSearchParams(window.location.search));
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [viewport, setViewport] = useState<TicketMapViewport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryEpoch, setRetryEpoch] = useState(0);
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
  const [openOnly, setOpenOnly] = useState(Boolean(initialFilters.openOnly));
  const [ticketIds, setTicketIds] = useState<string[]>(initialFilters.ticketIds ?? []);
  const [persistBounds, setPersistBounds] = useState(() => hasMapBounds(initialFilters));
  const [bounds, setBounds] = useState<MapBounds>(() =>
    hasMapBounds(initialFilters)
      ? {
          north: initialFilters.north as number,
          south: initialFilters.south as number,
          east: initialFilters.east as number,
          west: initialFilters.west as number,
          zoom: initialFilters.zoom ?? 15,
        }
      : DEFAULT_BOUNDS,
  );
  const hasLoaded = useRef(false);
  const requestGeneration = useRef(0);

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
    setOpenOnly(Boolean(filters.openOnly));
    setTicketIds(filters.ticketIds ?? []);
    if (hasMapBounds(filters)) {
      setPersistBounds(true);
      setBounds({
        north: filters.north as number,
        south: filters.south as number,
        east: filters.east as number,
        west: filters.west as number,
        zoom: filters.zoom ?? 15,
      });
    } else {
      setPersistBounds(false);
    }
  }

  const stateFilters = useMemo(
    () => ({
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
    }),
    [
      bounds,
      categoryFilter,
      departmentFilter,
      openOnly,
      persistBounds,
      statusFilter,
      ticketIds,
      urgencyCsv,
      urgencyFilter,
    ],
  );
  const { navigationFilters } = useDashboardLocationSync(stateFilters, applyNavigationFilters);

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
        setErrorMessage(error instanceof Error ? error.message : t('errors.loadTickets'));
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
    t,
    ticketIds,
    retryEpoch,
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
        t,
      ),
    [markers, t],
  );

  const pinSummary = useMemo(() => {
    if (clusters.length > 0 && markers.length === 0) {
      const total = clusters.reduce((sum, cluster) => sum + cluster.count, 0);
      return t('map.clusters', { count: clusters.length, total });
    }
    return `${t('map.pins', { count: markers.length })}${viewport?.truncated ? t('map.truncated') : ''}`;
  }, [clusters, markers.length, t, viewport?.truncated]);

  return (
    <DashboardLayout title={t('map.title')} subtitle={t('map.subtitle')}>
      {loadState === 'loading' && <LoadingState />}

      {loadState === 'error' && (
        <div className="map-view-page__error" role="alert">
          <h3>{t('tickets.unableLoad')}</h3>
          <p>{errorMessage}</p>
          <button type="button" onClick={() => setRetryEpoch((value) => value + 1)}>
            {t('common.tryAgain')}
          </button>
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
              <h3>{t('tickets.unableUpdate')}</h3>
              <p>{errorMessage}</p>
            </div>
          )}

          {markers.length === 0 && clusters.length === 0 && !hasActiveFilters && (
            <EmptyState title={t('map.emptyAreaTitle')} message={t('map.emptyAreaBody')} />
          )}

          {hasActiveFilters && markers.length === 0 && clusters.length === 0 && (
            <EmptyState
              title={
                ticketIds.length > 0 ? t('tickets.emptyGoneTitle') : t('tickets.emptyMatchTitle')
              }
              message={ticketIds.length > 0 ? t('map.emptyGoneBody') : t('tickets.emptyMatchBody')}
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

          <section className="map-view-page__list" aria-label={t('map.listA11y')}>
            <h2 className="map-view-page__list-title">{t('map.listTitle')}</h2>
            {markers.length === 0 ? (
              <p className="map-view-page__list-empty">
                {clusters.length > 0 ? t('map.zoomCluster') : t('map.noPins')}
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

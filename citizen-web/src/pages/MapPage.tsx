import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PublicReportsMap } from '@/components/PublicReportsMap';
import {
  PUBLIC_TICKETS_NETWORK_MESSAGE,
  getPublicMapViewport,
  type PublicMapViewport,
} from '@/services/tickets';
import type { PublicTicketMapViewportResponse } from '@/types/ticket';
import { useI18n } from '@/i18n/LocaleProvider';

const CACHE_FRESH_MS = 30_000;
const CACHE_MAX_ENTRIES = 40;
const mapCache = new Map<string, { data: PublicTicketMapViewportResponse; savedAt: number }>();

function cacheViewport(key: string, data: PublicTicketMapViewportResponse) {
  const now = Date.now();
  for (const [cachedKey, entry] of mapCache) {
    if (now - entry.savedAt >= CACHE_FRESH_MS) mapCache.delete(cachedKey);
  }
  mapCache.delete(key);
  mapCache.set(key, { data, savedAt: now });
  while (mapCache.size > CACHE_MAX_ENTRIES) {
    const oldest = mapCache.keys().next().value as string | undefined;
    if (!oldest) break;
    mapCache.delete(oldest);
  }
}

function viewportKey(viewport: PublicMapViewport) {
  const round = (value: number) => value.toFixed(2);
  return [
    round(viewport.north),
    round(viewport.south),
    round(viewport.east),
    round(viewport.west),
    Math.floor(viewport.zoom),
  ].join(':');
}

export function MapPage() {
  const { t } = useI18n();
  const [data, setData] = useState<PublicTicketMapViewportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const viewportRef = useRef<PublicMapViewport | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const requestRef = useRef(0);

  const load = useCallback(async (viewport: PublicMapViewport, force = false) => {
    viewportRef.current = viewport;
    const key = viewportKey(viewport);
    const cached = mapCache.get(key);
    if (!force && cached && Date.now() - cached.savedAt < CACHE_FRESH_MS) {
      setData(cached.data);
      setLoading(false);
      setError(null);
      return;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const requestId = ++requestRef.current;
    setLoading(true);
    setError(null);
    try {
      const result = await getPublicMapViewport(viewport, { signal: controller.signal });
      if (requestId !== requestRef.current) return;
      cacheViewport(key, result);
      setData(result);
    } catch (caught) {
      if (controller.signal.aborted || requestId !== requestRef.current) return;
      setError(
        caught instanceof Error && caught.message !== PUBLIC_TICKETS_NETWORK_MESSAGE
          ? caught.message
          : t('public.network'),
      );
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }, []);

  const handleViewportChange = useCallback(
    (viewport: PublicMapViewport) => {
      viewportRef.current = viewport;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => void load(viewport), 250);
    },
    [load],
  );

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      controllerRef.current?.abort();
    },
    [],
  );

  return (
    <div className="page">
      <h1>{t('public.mapTitle')}</h1>
      <p className="lede">{t('public.mapLede')}</p>
      <Link className="button button-secondary" to="/reports">
        {t('public.viewAsList')}
      </Link>

      {error ? (
        <div className="error-banner" role="alert">
          <p style={{ margin: '0 0 0.75rem' }}>{error}</p>
          <button
            type="button"
            className="button"
            onClick={() => viewportRef.current && void load(viewportRef.current, true)}
          >
            {t('common.tryAgain')}
          </button>
        </div>
      ) : null}

      <div className="stack">
        <PublicReportsMap data={data} onViewportChange={handleViewportChange} />
        {loading ? (
          <p className="muted" role="status">
            {t('public.updating')}
          </p>
        ) : null}
        {data?.truncated ? <p className="muted">{t('public.grouped')}</p> : null}
        {!loading && data && data.markers.length === 0 && data.clusters.length === 0 ? (
          <div className="empty-state compact">
            <span>⌖</span>
            <h2>{t('public.noReports')}</h2>
            <p>{t('public.emptyMap')}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

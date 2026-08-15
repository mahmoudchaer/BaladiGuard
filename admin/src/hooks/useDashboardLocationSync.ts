import { useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  parseDashboardSearchParams,
  serializeDashboardSearchParams,
  type DashboardNavigationFilters,
} from '@/utils/dashboardNavigation';

/**
 * Keep dashboard filter state aligned with the URL in both directions.
 * External navigations (assistant drill-down, back/forward) apply location → state.
 * Local filter edits write state → location. Self-writes are ignored so the two
 * sides cannot clobber each other when the page stays mounted on the same route.
 */
export function useDashboardLocationSync(
  stateFilters: DashboardNavigationFilters,
  applyFilters: (filters: DashboardNavigationFilters) => void,
) {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigationFilters = useMemo(() => parseDashboardSearchParams(searchParams), [searchParams]);
  const locationKey = searchParams.toString();
  const prevLocationRef = useRef(locationKey);
  const selfWriteRef = useRef(false);
  const applyRef = useRef(applyFilters);
  applyRef.current = applyFilters;

  useEffect(() => {
    const locationChanged = prevLocationRef.current !== locationKey;
    prevLocationRef.current = locationKey;

    if (locationChanged) {
      if (selfWriteRef.current) {
        selfWriteRef.current = false;
        return;
      }
      applyRef.current(navigationFilters);
      return;
    }

    const next = serializeDashboardSearchParams(stateFilters);
    const ownedCurrent = serializeDashboardSearchParams(navigationFilters).toString();
    if (ownedCurrent === next.toString()) {
      return;
    }
    selfWriteRef.current = true;
    setSearchParams(next, { replace: true });
  }, [locationKey, navigationFilters, setSearchParams, stateFilters]);

  return { searchParams, navigationFilters };
}

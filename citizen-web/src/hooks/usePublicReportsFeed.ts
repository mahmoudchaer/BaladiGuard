import { useCallback, useEffect, useRef, useState } from 'react';
import { PUBLIC_TICKETS_NETWORK_MESSAGE, getPublicTickets } from '@/services/tickets';
import type { PublicTicketResponse } from '@/types/ticket';

/** Safety bound so map auto-drain cannot loop forever (20 × 25 = 500 reports). */
export const PUBLIC_FEED_MAX_AUTO_PAGES = 25;

type UsePublicReportsFeedOptions = {
  /**
   * When true, keep fetching `nextCursor` pages after the initial load so the
   * public map does not silently stop at the first API page (#284 review).
   */
  autoLoadAll?: boolean;
  /** Cap on automatic page fetches; remaining pages stay reachable via loadMore. */
  maxAutoPages?: number;
};

export function usePublicReportsFeed({
  autoLoadAll = false,
  maxAutoPages = PUBLIC_FEED_MAX_AUTO_PAGES,
}: UsePublicReportsFeedOptions = {}) {
  const [items, setItems] = useState<PublicTicketResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pagesLoadedRef = useRef(0);

  const load = useCallback(
    async (cursor?: string | null) => {
      const appending = Boolean(cursor);
      if (appending) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setError(null);
        pagesLoadedRef.current = 0;
      }

      try {
        let pageCursor: string | null | undefined = cursor ?? null;
        let firstBatch = true;

        while (true) {
          const page = await getPublicTickets({
            limit: 20,
            cursor: pageCursor ?? null,
          });
          pagesLoadedRef.current += 1;
          setItems((prev) => (appending || !firstBatch ? [...prev, ...page.items] : page.items));
          setNextCursor(page.nextCursor);
          firstBatch = false;

          const shouldContinue =
            autoLoadAll && Boolean(page.nextCursor) && pagesLoadedRef.current < maxAutoPages;
          if (!shouldContinue) {
            break;
          }
          pageCursor = page.nextCursor;
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : PUBLIC_TICKETS_NETWORK_MESSAGE);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [autoLoadAll, maxAutoPages],
  );

  useEffect(() => {
    void load(null);
  }, [load]);

  return {
    items,
    nextCursor,
    loading,
    loadingMore,
    error,
    reload: () => load(null),
    loadMore: () => (nextCursor ? load(nextCursor) : Promise.resolve()),
  };
}

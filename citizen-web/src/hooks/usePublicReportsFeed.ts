import { useEffect, useState } from 'react';
import { PUBLIC_TICKETS_NETWORK_MESSAGE, getPublicTickets } from '@/services/tickets';
import type { PublicTicketResponse } from '@/types/ticket';

export function usePublicReportsFeed() {
  const [items, setItems] = useState<PublicTicketResponse[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (cursor?: string | null) => {
    const appending = Boolean(cursor);
    if (appending) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setError(null);
    }
    try {
      const page = await getPublicTickets({ limit: 20, cursor: cursor ?? null });
      setItems((prev) => (appending ? [...prev, ...page.items] : page.items));
      setNextCursor(page.nextCursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : PUBLIC_TICKETS_NETWORK_MESSAGE);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    void load(null);
  }, []);

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

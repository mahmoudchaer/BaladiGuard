import type { TicketListPage } from '@/types/ticketCollection';
import { getStoredStaffSession, STAFF_SESSION_CLEARED_EVENT } from '@/services/auth';

type CacheEntry = {
  page: TicketListPage;
  storedAtMs: number;
  freshnessHintSeconds: number;
};

const MAX_ENTRIES = 24;
const store = new Map<string, CacheEntry>();

if (typeof window !== 'undefined') {
  window.addEventListener(STAFF_SESSION_CLEARED_EVENT, () => {
    store.clear();
  });
}

function scopeKey(): string {
  const session = getStoredStaffSession();
  if (!session) {
    return 'anonymous';
  }
  return [
    session.staffId ?? session.username ?? 'staff',
    session.role ?? '',
    session.municipalityId ?? '',
    (session.departmentIds ?? []).join(','),
  ].join('|');
}

export function buildTicketListCacheKey(
  filters: Record<string, string | undefined>,
  cursor: string | null,
): string {
  const parts = Object.entries(filters)
    .filter(([, value]) => value && value !== 'ALL')
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`);
  return `${scopeKey()}::${parts.join('&')}::cursor=${cursor ?? ''}`;
}

export function readTicketListCache(key: string): TicketListPage | null {
  const entry = store.get(key);
  if (!entry) {
    return null;
  }
  // Move to end for LRU-ish behavior.
  store.delete(key);
  store.set(key, entry);
  return entry.page;
}

export function isTicketListCacheFresh(key: string, nowMs = Date.now()): boolean {
  const entry = store.get(key);
  if (!entry) {
    return false;
  }
  return nowMs - entry.storedAtMs < entry.freshnessHintSeconds * 1000;
}

export function writeTicketListCache(key: string, page: TicketListPage): void {
  store.set(key, {
    page,
    storedAtMs: Date.now(),
    freshnessHintSeconds: Math.max(5, page.freshnessHintSeconds || 30),
  });
  while (store.size > MAX_ENTRIES) {
    const oldest = store.keys().next().value;
    if (oldest === undefined) {
      break;
    }
    store.delete(oldest);
  }
}

export function invalidateTicketListCache(): void {
  store.clear();
}

export function invalidateTicketListCacheKeysMatching(ticketId: string): void {
  for (const [key, entry] of store.entries()) {
    if (entry.page.items.some((item) => item.ticketId === ticketId)) {
      store.delete(key);
    }
  }
}

import type {
  AiProcessingStatus,
  ActivityPage,
  DuplicateCandidate,
  DuplicateCandidatePage,
  DuplicateComparison,
  DuplicateLocation,
  PublicTicketStatus,
  StaffComment,
  Ticket,
  TicketAiFields,
  TicketAuditActionType,
  TicketAuditHistoryEntry,
  TicketDuplicateReference,
  TicketDuplicateSuggestion,
  TicketLocation,
  TicketStaffRole,
  TicketStatus,
  TicketStatusHistoryEntry,
} from '@/types/ticket';
import type {
  TicketAggregates,
  TicketListItem,
  TicketListPage,
  TicketMapViewport,
} from '@/types/ticketCollection';
import mockTickets from '../../../mock_tickets.json';
import { DEPARTMENT_NAMES } from '@/data/departments';
import { clearStoredStaffSession, getStaffAuthHeaders } from '@/services/auth';
import { config } from '@/services/config';
import {
  buildTicketListCacheKey,
  invalidateTicketListCache,
  invalidateTicketListCacheKeysMatching,
  isTicketListCacheFresh,
  readTicketListCache,
  writeTicketListCache,
} from '@/services/ticketListCache';
import { effectiveTicketCategory } from '@/utils/ticketCategory';
import { distanceMetersBetween } from '@/utils/ticketLocation';

const MOCK_LOAD_DELAY_MS = 350;
const DEFAULT_PAGE_LIMIT = 25;

export type FetchTicketsFilters = {
  status?: TicketStatus | 'ALL';
  category?: string | 'ALL';
  urgency?: Ticket['priority'] | 'ALL';
  departmentId?: string | 'ALL';
  slaState?: Ticket['sla'] extends infer S
    ? S extends { state: infer T }
      ? T | 'ALL'
      : never
    : never;
  assignmentState?: 'assigned' | 'unassigned' | 'ALL';
  q?: string;
  openOnly?: boolean;
};

export type FetchTicketsPageOptions = {
  filters?: FetchTicketsFilters;
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
  /** When true (default), serve fresh cache and revalidate stale entries. */
  useCache?: boolean;
};

export type TicketListPageResult = TicketListPage & {
  /** List projection mapped into the shared Ticket shape for existing UI. */
  tickets: Ticket[];
  fromCache: boolean;
  /**
   * When a stale cached page was returned, resolves with the fresh page.
   * Callers must apply it only if their request generation is still current.
   */
  revalidate?: Promise<TicketListPageResult>;
};

export type FetchTicketMapOptions = {
  north: number;
  south: number;
  east: number;
  west: number;
  zoom: number;
  filters?: FetchTicketsFilters;
  limit?: number;
  signal?: AbortSignal;
};

/**
 * Session-scoped mock merge state so a mock merge behaves like real
 * persistence: every member ticket reflects the group on subsequent reads.
 */
const mockMergeGroups = new Map<string, TicketDuplicateReference>();
const mockTicketGroupIds = new Map<string, string>();

function applyMockMergeState(ticket: Ticket): Ticket {
  const mergedGroupId = mockTicketGroupIds.get(ticket.ticketId);
  if (!mergedGroupId) {
    return ticket;
  }
  return {
    ...ticket,
    duplicateGroupId: mergedGroupId,
    duplicateGroup: mockMergeGroups.get(mergedGroupId) ?? null,
  };
}

function isTicketArray(value: unknown): value is Ticket[] {
  return Array.isArray(value);
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError';
}

async function readApiErrorMessage(response: Response, fallbackMessage: string): Promise<string> {
  const errorBody = await response.json().catch(() => null);
  const error = isRecord(errorBody) && isRecord(errorBody.error) ? errorBody.error : null;
  const message = error ? error.message : null;
  const details = error ? error.details : null;

  if (Array.isArray(details) && details.length > 0) {
    const detailMessages = details
      .map((detail: unknown) => {
        if (!isRecord(detail) || typeof detail.message !== 'string') {
          return null;
        }

        return typeof detail.field === 'string'
          ? `${detail.field}: ${detail.message}`
          : detail.message;
      })
      .filter(Boolean);

    if (detailMessages.length > 0) {
      return `${typeof message === 'string' ? message : fallbackMessage} ${detailMessages.join(' ')}`;
    }
  }

  return typeof message === 'string' ? message : fallbackMessage;
}

async function throwApiError(response: Response, fallbackMessage: string): Promise<never> {
  if (response.status === 401) {
    clearStoredStaffSession();
    invalidateTicketListCache();
  }

  const message = await readApiErrorMessage(response, fallbackMessage);
  throw new Error(message);
}

function ticketMatchesFetchFilters(ticket: Ticket, filters: FetchTicketsFilters): boolean {
  if (filters.status && filters.status !== 'ALL' && ticket.status !== filters.status) {
    return false;
  }
  if (filters.category && filters.category !== 'ALL' && ticket.category !== filters.category) {
    return false;
  }
  if (filters.urgency && filters.urgency !== 'ALL' && ticket.priority !== filters.urgency) {
    return false;
  }
  if (
    filters.departmentId &&
    filters.departmentId !== 'ALL' &&
    ticket.departmentId !== filters.departmentId
  ) {
    return false;
  }
  if (filters.slaState && filters.slaState !== 'ALL' && ticket.sla?.state !== filters.slaState) {
    return false;
  }
  if (filters.assignmentState === 'unassigned' && ticket.departmentId) {
    return false;
  }
  if (filters.assignmentState === 'assigned' && !ticket.departmentId) {
    return false;
  }
  if (filters.openOnly) {
    const open = new Set(['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS']);
    if (!open.has(ticket.status)) {
      return false;
    }
  }
  const query = filters.q?.trim().toLowerCase();
  if (query) {
    const haystack = [
      ticket.ticketId,
      ticket.ticketNumber,
      ticket.description,
      ticket.location.addressText,
    ]
      .join(' ')
      .toLowerCase();
    if (!haystack.includes(query)) {
      return false;
    }
  }
  return true;
}

function filterRecord(filters: FetchTicketsFilters = {}): Record<string, string | undefined> {
  return {
    status: filters.status && filters.status !== 'ALL' ? filters.status : undefined,
    category: filters.category && filters.category !== 'ALL' ? filters.category : undefined,
    urgency: filters.urgency && filters.urgency !== 'ALL' ? filters.urgency : undefined,
    departmentId:
      filters.departmentId && filters.departmentId !== 'ALL' ? filters.departmentId : undefined,
    slaState: filters.slaState && filters.slaState !== 'ALL' ? filters.slaState : undefined,
    assignmentState:
      filters.assignmentState && filters.assignmentState !== 'ALL'
        ? filters.assignmentState
        : undefined,
    q: filters.q?.trim() ? filters.q.trim() : undefined,
    openOnly: filters.openOnly ? 'true' : undefined,
  };
}

function appendListFilters(url: URL, filters: FetchTicketsFilters = {}): void {
  if (filters.status && filters.status !== 'ALL') {
    url.searchParams.set('status', filters.status);
  }
  if (filters.category && filters.category !== 'ALL') {
    url.searchParams.set('category', filters.category);
  }
  if (filters.urgency && filters.urgency !== 'ALL') {
    url.searchParams.set('urgency', filters.urgency);
  }
  if (filters.departmentId && filters.departmentId !== 'ALL') {
    url.searchParams.set('departmentId', filters.departmentId);
  }
  if (filters.slaState && filters.slaState !== 'ALL') {
    url.searchParams.set('slaState', filters.slaState);
  }
  if (filters.assignmentState && filters.assignmentState !== 'ALL') {
    url.searchParams.set('assignmentState', filters.assignmentState);
  }
  const query = filters.q?.trim();
  if (query) {
    url.searchParams.set('q', query);
  }
  if (filters.openOnly) {
    url.searchParams.set('openOnly', 'true');
  }
}

function listItemToTicket(item: TicketListItem): Ticket {
  const departmentName = item.department?.name ?? undefined;
  const departmentId = item.departmentId ?? item.department?.departmentId ?? null;
  return {
    ticketId: item.ticketId,
    ticketNumber: item.ticketNumber?.trim() || item.ticketId,
    trackingCode: '',
    description: item.summary,
    contact: {},
    location: {
      latitude: item.location.latitude,
      longitude: item.location.longitude,
      addressText: item.location.addressText,
      source: 'GPS',
    },
    imageObjectKey: 'unavailable',
    status: item.status,
    category: item.category,
    priority: item.priority,
    createdBy: null,
    municipalityId: item.municipalityId,
    departmentId,
    departmentName,
    department:
      departmentId || departmentName
        ? {
            departmentId: departmentId ?? undefined,
            name: departmentName,
          }
        : null,
    duplicateGroupId: null,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
  };
}

function normalizeTicketListItem(data: unknown): TicketListItem {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    throw new Error('Unexpected ticket list item shape.');
  }
  const location = isRecord(data.location) ? data.location : {};
  const department = isRecord(data.department) ? data.department : null;
  const status = normalizeTicketStatus(data.status);
  const priority =
    data.priority === 'low' ||
    data.priority === 'medium' ||
    data.priority === 'high' ||
    data.priority === 'critical'
      ? data.priority
      : null;

  return {
    ticketId: data.ticketId,
    ticketNumber: typeof data.ticketNumber === 'string' ? data.ticketNumber : null,
    status,
    category: typeof data.category === 'string' ? data.category : 'PENDING_CLASSIFICATION',
    priority,
    departmentId: typeof data.departmentId === 'string' ? data.departmentId : null,
    department: department
      ? {
          departmentId:
            typeof department.departmentId === 'string' ? department.departmentId : null,
          name: typeof department.name === 'string' ? department.name : null,
        }
      : null,
    summary: typeof data.summary === 'string' ? data.summary : '',
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    updatedAt: typeof data.updatedAt === 'string' ? data.updatedAt : null,
    municipalityId: typeof data.municipalityId === 'string' ? data.municipalityId : null,
    assignmentState: data.assignmentState === 'unassigned' ? 'unassigned' : 'assigned',
    location: {
      latitude: typeof location.latitude === 'number' ? location.latitude : Number.NaN,
      longitude: typeof location.longitude === 'number' ? location.longitude : Number.NaN,
      addressText: typeof location.addressText === 'string' ? location.addressText.trim() : '',
    },
  };
}

function normalizeTicketListPage(data: unknown): TicketListPage {
  if (!isRecord(data) || !Array.isArray(data.items)) {
    throw new Error('Unexpected ticket list response shape.');
  }
  return {
    items: data.items.map((item) => normalizeTicketListItem(item)),
    nextCursor: typeof data.nextCursor === 'string' ? data.nextCursor : null,
    previousCursor: typeof data.previousCursor === 'string' ? data.previousCursor : null,
    limit: typeof data.limit === 'number' ? data.limit : DEFAULT_PAGE_LIMIT,
    scannedCount: typeof data.scannedCount === 'number' ? data.scannedCount : null,
    approximateTotal: typeof data.approximateTotal === 'number' ? data.approximateTotal : null,
    freshnessHintSeconds:
      typeof data.freshnessHintSeconds === 'number' ? data.freshnessHintSeconds : 30,
  };
}

function pageResultFromPage(page: TicketListPage, fromCache: boolean): TicketListPageResult {
  return {
    ...page,
    tickets: page.items.map(listItemToTicket),
    fromCache,
  };
}

async function fetchMockTickets(filters: FetchTicketsFilters = {}): Promise<Ticket[]> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LOAD_DELAY_MS));

  if (!isTicketArray(mockTickets)) {
    throw new Error('Invalid mock ticket fixtures.');
  }

  return [...mockTickets]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .map((ticket) => applyMockMergeState(ticket))
    .filter((ticket) => ticketMatchesFetchFilters(ticket, filters));
}

function ticketToListItem(ticket: Ticket): TicketListItem {
  return {
    ticketId: ticket.ticketId,
    ticketNumber: ticket.ticketNumber,
    status: ticket.status,
    category: ticket.category,
    priority: ticket.priority,
    departmentId: ticket.departmentId,
    department: ticket.departmentId
      ? {
          departmentId: ticket.departmentId,
          name: ticket.departmentName ?? ticket.department?.name ?? null,
        }
      : null,
    summary: ticket.description,
    createdAt: ticket.createdAt,
    updatedAt: ticket.updatedAt,
    municipalityId: ticket.municipalityId,
    assignmentState: ticket.departmentId ? 'assigned' : 'unassigned',
    location: {
      latitude: ticket.location.latitude,
      longitude: ticket.location.longitude,
      addressText: ticket.location.addressText,
    },
  };
}

async function fetchMockTicketsPage(
  options: FetchTicketsPageOptions = {},
): Promise<TicketListPageResult> {
  const filters = options.filters ?? {};
  const limit = options.limit ?? DEFAULT_PAGE_LIMIT;
  const all = await fetchMockTickets(filters);
  const start = options.cursor ? Number.parseInt(options.cursor, 10) || 0 : 0;
  const slice = all.slice(start, start + limit);
  const nextStart = start + limit;
  const page: TicketListPage = {
    items: slice.map(ticketToListItem),
    nextCursor: nextStart < all.length ? String(nextStart) : null,
    previousCursor: start > 0 ? String(Math.max(0, start - limit)) : null,
    limit,
    scannedCount: all.length,
    approximateTotal: all.length,
    freshnessHintSeconds: 30,
  };
  return pageResultFromPage(page, false);
}

function buildTicketListUrl(
  filters: FetchTicketsFilters = {},
  cursor: string | null = null,
  limit = DEFAULT_PAGE_LIMIT,
): string {
  const url = new URL(`${config.apiBaseUrl}/v1/tickets`);
  appendListFilters(url, filters);
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }
  if (limit !== DEFAULT_PAGE_LIMIT) {
    url.searchParams.set('limit', String(limit));
  }
  return url.toString();
}

async function fetchTicketsPageFromApi(
  options: FetchTicketsPageOptions = {},
): Promise<TicketListPage> {
  const filters = options.filters ?? {};
  const cursor = options.cursor ?? null;
  const limit = options.limit ?? DEFAULT_PAGE_LIMIT;
  const response = await fetch(buildTicketListUrl(filters, cursor, limit), {
    headers: {
      ...getStaffAuthHeaders(),
    },
    signal: options.signal,
  });

  if (!response.ok) {
    await throwApiError(response, 'Unable to load tickets from the server.');
  }

  const data: unknown = await response.json();
  return normalizeTicketListPage(data);
}

export async function fetchTicketsPage(
  options: FetchTicketsPageOptions = {},
): Promise<TicketListPageResult> {
  if (options.signal?.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError');
  }

  if (config.useMockData) {
    return fetchMockTicketsPage(options);
  }

  const filters = options.filters ?? {};
  const cursor = options.cursor ?? null;
  const useCache = options.useCache !== false;
  const cacheKey = buildTicketListCacheKey(filterRecord(filters), cursor);

  if (useCache) {
    const cached = readTicketListCache(cacheKey);
    if (cached && isTicketListCacheFresh(cacheKey)) {
      return pageResultFromPage(cached, true);
    }
    if (cached) {
      // Stale-while-revalidate: return cached page immediately and expose a
      // promise so the caller can apply the fresh page when it arrives.
      const revalidate = fetchTicketsPageFromApi({ ...options, signal: undefined }).then((page) => {
        writeTicketListCache(cacheKey, page);
        if (page.nextCursor) {
          const nextKey = buildTicketListCacheKey(filterRecord(filters), page.nextCursor);
          if (!isTicketListCacheFresh(nextKey)) {
            void fetchTicketsPageFromApi({
              filters,
              cursor: page.nextCursor,
              limit: options.limit,
            })
              .then((nextPage) => writeTicketListCache(nextKey, nextPage))
              .catch(() => undefined);
          }
        }
        return pageResultFromPage(page, false);
      });
      return {
        ...pageResultFromPage(cached, true),
        revalidate,
      };
    }
  }

  const page = await fetchTicketsPageFromApi(options);
  writeTicketListCache(cacheKey, page);

  if (page.nextCursor && useCache) {
    const nextKey = buildTicketListCacheKey(filterRecord(filters), page.nextCursor);
    if (!isTicketListCacheFresh(nextKey)) {
      void fetchTicketsPageFromApi({
        filters,
        cursor: page.nextCursor,
        limit: options.limit,
      })
        .then((nextPage) => writeTicketListCache(nextKey, nextPage))
        .catch(() => undefined);
    }
  }

  return pageResultFromPage(page, false);
}

/**
 * Convenience wrapper that returns the current page of tickets as Ticket[].
 * Prefer fetchTicketsPage for pagination, cache, and AbortSignal support.
 */
export async function fetchTickets(
  filters: FetchTicketsFilters = {},
  options: Omit<FetchTicketsPageOptions, 'filters'> = {},
): Promise<Ticket[]> {
  try {
    const page = await fetchTicketsPage({ ...options, filters });
    return page.tickets;
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw error;
  }
}

function normalizeTicketAggregates(data: unknown): TicketAggregates {
  if (!isRecord(data)) {
    throw new Error('Unexpected ticket aggregates response shape.');
  }
  return {
    openCount: typeof data.openCount === 'number' ? data.openCount : 0,
    criticalCount: typeof data.criticalCount === 'number' ? data.criticalCount : 0,
    highCount: typeof data.highCount === 'number' ? data.highCount : 0,
    unassignedCount: typeof data.unassignedCount === 'number' ? data.unassignedCount : 0,
    overdueCount: typeof data.overdueCount === 'number' ? data.overdueCount : 0,
    approximate: Boolean(data.approximate),
  };
}

export async function fetchTicketAggregates(signal?: AbortSignal): Promise<TicketAggregates> {
  if (config.useMockData) {
    const tickets = await fetchMockTickets();
    const open = new Set(['SUBMITTED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS']);
    return {
      openCount: tickets.filter((ticket) => open.has(ticket.status)).length,
      criticalCount: tickets.filter((ticket) => ticket.priority === 'critical').length,
      highCount: tickets.filter((ticket) => ticket.priority === 'high').length,
      unassignedCount: tickets.filter((ticket) => !ticket.departmentId).length,
      overdueCount: tickets.filter((ticket) => ticket.sla?.state === 'overdue').length,
      approximate: false,
    };
  }

  const response = await fetch(`${config.apiBaseUrl}/v1/tickets/aggregates`, {
    headers: {
      ...getStaffAuthHeaders(),
    },
    signal,
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load ticket aggregates.');
  }
  return normalizeTicketAggregates(await response.json());
}

function normalizeTicketMapViewport(data: unknown): TicketMapViewport {
  if (!isRecord(data) || !Array.isArray(data.markers) || !Array.isArray(data.clusters)) {
    throw new Error('Unexpected ticket map response shape.');
  }

  return {
    markers: data.markers.filter(isRecord).flatMap((marker) => {
      if (typeof marker.ticketId !== 'string') {
        return [];
      }
      return [
        {
          ticketId: marker.ticketId,
          ticketNumber: typeof marker.ticketNumber === 'string' ? marker.ticketNumber : null,
          status: normalizeTicketStatus(marker.status),
          priority:
            marker.priority === 'low' ||
            marker.priority === 'medium' ||
            marker.priority === 'high' ||
            marker.priority === 'critical'
              ? marker.priority
              : null,
          latitude: typeof marker.latitude === 'number' ? marker.latitude : Number.NaN,
          longitude: typeof marker.longitude === 'number' ? marker.longitude : Number.NaN,
          category:
            typeof marker.category === 'string' ? marker.category : 'PENDING_CLASSIFICATION',
        },
      ];
    }),
    clusters: data.clusters.filter(isRecord).flatMap((cluster) => {
      if (typeof cluster.id !== 'string' || typeof cluster.count !== 'number') {
        return [];
      }
      return [
        {
          id: cluster.id,
          latitude: typeof cluster.latitude === 'number' ? cluster.latitude : Number.NaN,
          longitude: typeof cluster.longitude === 'number' ? cluster.longitude : Number.NaN,
          count: cluster.count,
        },
      ];
    }),
    limit: typeof data.limit === 'number' ? data.limit : 200,
    truncated: Boolean(data.truncated),
    zoom: typeof data.zoom === 'number' ? data.zoom : 12,
  };
}

export async function fetchTicketMapViewport(
  options: FetchTicketMapOptions,
): Promise<TicketMapViewport> {
  if (config.useMockData) {
    const tickets = await fetchMockTickets(options.filters ?? {});
    const markers = tickets
      .filter(
        (ticket) =>
          Number.isFinite(ticket.location.latitude) &&
          Number.isFinite(ticket.location.longitude) &&
          ticket.location.latitude >= options.south &&
          ticket.location.latitude <= options.north &&
          ticket.location.longitude >= options.west &&
          ticket.location.longitude <= options.east,
      )
      .slice(0, options.limit ?? 200)
      .map((ticket) => ({
        ticketId: ticket.ticketId,
        ticketNumber: ticket.ticketNumber,
        status: ticket.status,
        priority: ticket.priority,
        latitude: ticket.location.latitude,
        longitude: ticket.location.longitude,
        category: ticket.category,
      }));
    return {
      markers: options.zoom < 14 ? [] : markers,
      clusters:
        options.zoom < 14 && markers.length > 0
          ? [
              {
                id: 'mock-cluster',
                latitude: markers.reduce((sum, m) => sum + m.latitude, 0) / markers.length,
                longitude: markers.reduce((sum, m) => sum + m.longitude, 0) / markers.length,
                count: markers.length,
              },
            ]
          : [],
      limit: options.limit ?? 200,
      truncated: false,
      zoom: options.zoom,
    };
  }

  const url = new URL(`${config.apiBaseUrl}/v1/tickets/map`);
  url.searchParams.set('north', String(options.north));
  url.searchParams.set('south', String(options.south));
  url.searchParams.set('east', String(options.east));
  url.searchParams.set('west', String(options.west));
  url.searchParams.set('zoom', String(options.zoom));
  appendListFilters(url, options.filters ?? {});
  if (options.limit) {
    url.searchParams.set('limit', String(options.limit));
  }

  const response = await fetch(url.toString(), {
    headers: {
      ...getStaffAuthHeaders(),
    },
    signal: options.signal,
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load map tickets.');
  }
  return normalizeTicketMapViewport(await response.json());
}

function invalidateCachesForTicket(ticketId: string): void {
  invalidateTicketListCacheKeysMatching(ticketId);
}

export { invalidateTicketListCache };

function buildMockGroupReference(
  tickets: Ticket[],
  duplicateGroupId: string,
): TicketDuplicateReference {
  const sessionGroup = mockMergeGroups.get(duplicateGroupId);
  if (sessionGroup) {
    return sessionGroup;
  }

  // Static fixture groups carry no canonical marker, so derive it from the
  // group data: the earliest-created member is the original report.
  const members = tickets
    .filter((item) => item.duplicateGroupId === duplicateGroupId)
    .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());

  return {
    duplicateGroupId,
    ticketIds: members.map((item) => item.ticketId),
    canonicalTicketId: members[0]?.ticketId,
  };
}

async function fetchMockTicketById(ticketId: string): Promise<Ticket | null> {
  const tickets = await fetchMockTickets();
  const ticket = tickets.find((item) => item.ticketId === ticketId) ?? null;
  if (!ticket?.duplicateGroupId) {
    return ticket;
  }

  return {
    ...ticket,
    duplicateGroup: buildMockGroupReference(tickets, ticket.duplicateGroupId),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function normalizeAiProcessingStatus(value: unknown): AiProcessingStatus | undefined {
  if (
    value === 'pending' ||
    value === 'processing' ||
    value === 'completed' ||
    value === 'failed'
  ) {
    return value;
  }
  return undefined;
}

function normalizeDuplicateGroup(data: unknown): TicketDuplicateReference | null {
  if (!isRecord(data) || typeof data.duplicateGroupId !== 'string') {
    return null;
  }

  const ticketIds = Array.isArray(data.ticketIds)
    ? data.ticketIds.filter((value): value is string => typeof value === 'string')
    : undefined;

  return {
    duplicateGroupId: data.duplicateGroupId,
    ticketIds,
    canonicalTicketId:
      typeof data.canonicalTicketId === 'string' ? data.canonicalTicketId : undefined,
  };
}

function normalizeTicketStatus(value: unknown): TicketStatus {
  if (
    value === 'SUBMITTED' ||
    value === 'UNDER_REVIEW' ||
    value === 'ASSIGNED' ||
    value === 'IN_PROGRESS' ||
    value === 'RESOLVED' ||
    value === 'CLOSED'
  ) {
    return value;
  }

  return 'SUBMITTED';
}

function normalizeDuplicateSuggestions(data: unknown): TicketDuplicateSuggestion[] {
  if (!Array.isArray(data)) {
    return [];
  }

  return data.filter(isRecord).flatMap((suggestion) => {
    if (typeof suggestion.ticketId !== 'string' || typeof suggestion.category !== 'string') {
      return [];
    }

    const distanceMeters =
      typeof suggestion.distanceMeters === 'number' && Number.isFinite(suggestion.distanceMeters)
        ? suggestion.distanceMeters
        : null;
    if (distanceMeters === null) {
      return [];
    }

    const normalized: TicketDuplicateSuggestion = {
      ticketId: suggestion.ticketId,
      distanceMeters,
      status: normalizeTicketStatus(suggestion.status),
      category: suggestion.category,
    };

    if (typeof suggestion.ticketNumber === 'string') {
      normalized.ticketNumber = suggestion.ticketNumber;
    }
    if (typeof suggestion.score === 'number') {
      normalized.score = suggestion.score;
    }
    if (suggestion.categoryMatch === 'same' || suggestion.categoryMatch === 'similar') {
      normalized.categoryMatch = suggestion.categoryMatch;
    }

    return [normalized];
  });
}

function normalizeStatusHistory(data: unknown): TicketStatusHistoryEntry[] {
  if (!Array.isArray(data)) {
    return [];
  }

  return data.filter(isRecord).flatMap((entry) => {
    // Drop invalid statuses instead of coercing them to SUBMITTED.
    if (
      entry.status !== 'SUBMITTED' &&
      entry.status !== 'UNDER_REVIEW' &&
      entry.status !== 'ASSIGNED' &&
      entry.status !== 'IN_PROGRESS' &&
      entry.status !== 'RESOLVED' &&
      entry.status !== 'CLOSED'
    ) {
      return [];
    }

    const changedAt = typeof entry.changedAt === 'string' ? entry.changedAt.trim() : '';
    if (!changedAt || Number.isNaN(Date.parse(changedAt))) {
      return [];
    }

    const normalized: TicketStatusHistoryEntry = {
      status: entry.status,
      changedAt,
    };

    if (typeof entry.changedBy === 'string' && entry.changedBy.trim().length > 0) {
      normalized.changedBy = entry.changedBy.trim();
    }
    if (typeof entry.note === 'string' && entry.note.trim().length > 0) {
      normalized.note = entry.note.trim();
    }

    return [normalized];
  });
}

const AUDIT_ACTION_TYPES: readonly TicketAuditActionType[] = [
  'STATUS_CHANGE',
  'CATEGORY_REVIEW',
  'DEPARTMENT_ASSIGN',
  'DUPLICATE_MERGE',
  'PUBLIC_CONTENT_UPDATE',
];

function normalizeAuditActionType(value: unknown): TicketAuditActionType | null {
  return AUDIT_ACTION_TYPES.find((actionType) => actionType === value) ?? null;
}

function normalizeAuditActorRole(value: unknown): TicketStaffRole | undefined {
  return value === 'municipal_staff' || value === 'administrator' ? value : undefined;
}

function optionalTrimmedString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined;
}

/**
 * Staff-only audit rows. Entries without a usable action type or timestamp are
 * dropped so a partially malformed audit trail never breaks the ticket read.
 */
function normalizeAuditHistory(data: unknown): TicketAuditHistoryEntry[] {
  if (!Array.isArray(data)) {
    return [];
  }

  return data.filter(isRecord).flatMap((entry) => {
    const actionType = normalizeAuditActionType(entry.actionType);
    if (!actionType) {
      return [];
    }

    const changedAt = typeof entry.changedAt === 'string' ? entry.changedAt.trim() : '';
    if (!changedAt || Number.isNaN(Date.parse(changedAt))) {
      return [];
    }

    const normalized: TicketAuditHistoryEntry = {
      actionType,
      summary: optionalTrimmedString(entry.summary) ?? '',
      changedAt,
    };

    const actorId = optionalTrimmedString(entry.actorId);
    if (actorId) {
      normalized.actorId = actorId;
    }
    const actorRole = normalizeAuditActorRole(entry.actorRole);
    if (actorRole) {
      normalized.actorRole = actorRole;
    }
    const previousValue = optionalTrimmedString(entry.previousValue);
    if (previousValue) {
      normalized.previousValue = previousValue;
    }
    const newValue = optionalTrimmedString(entry.newValue);
    if (newValue) {
      normalized.newValue = newValue;
    }

    return [normalized];
  });
}

function normalizeTicketAiFields(data: unknown): TicketAiFields | undefined {
  if (!isRecord(data)) {
    return undefined;
  }

  const aiProcessingStatus = normalizeAiProcessingStatus(data.aiProcessingStatus);
  const aiConfidence = typeof data.aiConfidence === 'number' ? data.aiConfidence : undefined;

  const ai: TicketAiFields = {
    originalDescription:
      typeof data.originalDescription === 'string' ? data.originalDescription : undefined,
    cleanedDescription:
      typeof data.cleanedDescription === 'string' ? data.cleanedDescription : undefined,
    aiSuggestedCategory:
      typeof data.aiSuggestedCategory === 'string' ? data.aiSuggestedCategory : undefined,
    aiCategoryExplanation:
      typeof data.aiCategoryExplanation === 'string' ? data.aiCategoryExplanation : undefined,
    aiConfidence,
    finalCategory: typeof data.finalCategory === 'string' ? data.finalCategory : undefined,
    categoryReviewedBy:
      typeof data.categoryReviewedBy === 'string' ? data.categoryReviewedBy : undefined,
    categoryReviewedAt:
      typeof data.categoryReviewedAt === 'string' ? data.categoryReviewedAt : undefined,
    aiProcessingStatus,
    aiModelVersion: typeof data.aiModelVersion === 'string' ? data.aiModelVersion : undefined,
    suggestedCategory:
      typeof data.suggestedCategory === 'string' ? data.suggestedCategory : undefined,
    suggestedDepartmentId:
      typeof data.suggestedDepartmentId === 'string' ? data.suggestedDepartmentId : undefined,
    urgencyScore: typeof data.urgencyScore === 'number' ? data.urgencyScore : undefined,
    urgencyReason: typeof data.urgencyReason === 'string' ? data.urgencyReason : undefined,
    summary: typeof data.summary === 'string' ? data.summary : undefined,
  };

  const hasAiData = Object.values(ai).some((value) => value !== undefined);
  return hasAiData ? ai : undefined;
}

function normalizeTicketSla(data: unknown): Ticket['sla'] {
  if (!isRecord(data)) return undefined;
  const states = ['on_track', 'due_soon', 'overdue', 'completed', 'unavailable'] as const;
  const state = data.state;
  if (!states.includes(state as (typeof states)[number])) return undefined;
  return {
    state: state as (typeof states)[number],
    acknowledgementDueAt:
      typeof data.acknowledgementDueAt === 'string' ? data.acknowledgementDueAt : null,
    resolutionDueAt: typeof data.resolutionDueAt === 'string' ? data.resolutionDueAt : null,
    targetAt: typeof data.targetAt === 'string' ? data.targetAt : null,
    remainingSeconds: typeof data.remainingSeconds === 'number' ? data.remainingSeconds : null,
    overdueSeconds: typeof data.overdueSeconds === 'number' ? data.overdueSeconds : null,
    policyKey:
      data.policyKey === 'low' ||
      data.policyKey === 'medium' ||
      data.policyKey === 'high' ||
      data.policyKey === 'critical'
        ? data.policyKey
        : null,
  };
}

function normalizeTicketLocation(data: unknown): TicketLocation {
  // Tolerant for list/detail reads: one malformed ticket must not fail the whole fetch.
  // Invalid coordinates are filtered later when plotting pins (getPlottableTickets).
  if (!isRecord(data)) {
    return {
      latitude: Number.NaN,
      longitude: Number.NaN,
      addressText: '',
      source: 'PLACEHOLDER',
    };
  }

  const { latitude, longitude, addressText, source } = data;
  const hasValidLatitude =
    typeof latitude === 'number' && Number.isFinite(latitude) && latitude >= -90 && latitude <= 90;
  const hasValidLongitude =
    typeof longitude === 'number' &&
    Number.isFinite(longitude) &&
    longitude >= -180 &&
    longitude <= 180;
  const normalizedAddress = typeof addressText === 'string' ? addressText.trim() : '';
  const hasValidSource = source === 'GPS' || source === 'MANUAL' || source === 'PLACEHOLDER';

  return {
    latitude: hasValidLatitude ? latitude : Number.NaN,
    longitude: hasValidLongitude ? longitude : Number.NaN,
    addressText: normalizedAddress,
    source: hasValidSource ? source : 'PLACEHOLDER',
  };
}

function normalizeTicketFromApi(data: unknown): Ticket {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    throw new Error('Unexpected ticket response shape.');
  }

  const location = normalizeTicketLocation(data.location);
  const department = isRecord(data.department) ? data.department : null;
  const imageReferences = Array.isArray(data.imageReferences)
    ? data.imageReferences.filter(isRecord)
    : [];
  const primaryImage = imageReferences[0];

  const ticketNumber =
    typeof data.ticketNumber === 'string' && data.ticketNumber.trim().length > 0
      ? data.ticketNumber
      : data.ticketId;

  const trackingCode =
    typeof data.trackingCode === 'string' && data.trackingCode.trim().length > 0
      ? data.trackingCode
      : 'N/A';

  const resolvedImageObjectKey =
    typeof data.imageObjectKey === 'string' && data.imageObjectKey.trim().length > 0
      ? data.imageObjectKey
      : typeof primaryImage?.objectKey === 'string'
        ? primaryImage.objectKey
        : 'unavailable';

  const resolvedImageUrl = typeof primaryImage?.url === 'string' ? primaryImage.url : undefined;
  const resolvedDepartmentId =
    typeof data.departmentId === 'string'
      ? data.departmentId
      : typeof department?.departmentId === 'string'
        ? department.departmentId
        : null;
  const resolvedDepartmentName = typeof department?.name === 'string' ? department.name : undefined;

  return {
    ticketId: data.ticketId,
    ticketNumber,
    trackingCode,
    description: typeof data.description === 'string' ? data.description : '',
    contact: isRecord(data.contact)
      ? {
          name: typeof data.contact.name === 'string' ? data.contact.name : undefined,
          phone: typeof data.contact.phone === 'string' ? data.contact.phone : undefined,
          email: typeof data.contact.email === 'string' ? data.contact.email : undefined,
        }
      : {},
    location,
    imageObjectKey: resolvedImageObjectKey,
    imageUrl: resolvedImageUrl,
    imageReferences: imageReferences.map((reference) => ({
      objectKey: typeof reference.objectKey === 'string' ? reference.objectKey : 'unavailable',
      url: typeof reference.url === 'string' ? reference.url : undefined,
      contentType: typeof reference.contentType === 'string' ? reference.contentType : undefined,
      createdAt: typeof reference.createdAt === 'string' ? reference.createdAt : undefined,
    })),
    status: normalizeTicketStatus(data.status),
    category: typeof data.category === 'string' ? data.category : 'PENDING_CLASSIFICATION',
    priority:
      data.priority === 'low' ||
      data.priority === 'medium' ||
      data.priority === 'high' ||
      data.priority === 'critical'
        ? data.priority
        : null,
    createdBy: typeof data.createdBy === 'string' ? data.createdBy : null,
    municipalityId: typeof data.municipalityId === 'string' ? data.municipalityId : null,
    departmentId: resolvedDepartmentId,
    departmentName: resolvedDepartmentName,
    department:
      department && (department.departmentId || department.name)
        ? {
            departmentId:
              typeof department.departmentId === 'string' ? department.departmentId : undefined,
            name: typeof department.name === 'string' ? department.name : undefined,
          }
        : null,
    duplicateGroupId: typeof data.duplicateGroupId === 'string' ? data.duplicateGroupId : null,
    duplicateGroup: normalizeDuplicateGroup(data.duplicateGroup),
    duplicateSuggestions: normalizeDuplicateSuggestions(data.duplicateSuggestions),
    statusHistory: normalizeStatusHistory(data.statusHistory),
    auditHistory: normalizeAuditHistory(data.auditHistory),
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    updatedAt: typeof data.updatedAt === 'string' ? data.updatedAt : null,
    updatedBy: typeof data.updatedBy === 'string' ? data.updatedBy : null,
    ai: normalizeTicketAiFields(data.ai),
    sla: normalizeTicketSla(data.sla),
    public: normalizeTicketPublicFields(data.public),
  };
}

function normalizeTicketPublicFields(data: unknown): Ticket['public'] {
  if (!isRecord(data)) {
    return undefined;
  }
  const status = data.status;
  if (status !== 'DRAFT' && status !== 'PUBLISHED' && status !== 'UNPUBLISHED') {
    return undefined;
  }
  return {
    status,
    description: typeof data.description === 'string' ? data.description : null,
    locationLabel: typeof data.locationLabel === 'string' ? data.locationLabel : null,
    imageObjectKey: typeof data.imageObjectKey === 'string' ? data.imageObjectKey : null,
    publishedAt: typeof data.publishedAt === 'string' ? data.publishedAt : null,
  };
}

async function fetchTicketByIdFromApi(ticketId: string): Promise<Ticket | null> {
  const response = await fetch(`${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}`, {
    headers: {
      ...getStaffAuthHeaders(),
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to load ticket from the server.');
  }

  const data: unknown = await response.json();
  return normalizeTicketFromApi(data);
}

export async function fetchTicketById(ticketId: string): Promise<Ticket | null> {
  if (config.useMockData) {
    return fetchMockTicketById(ticketId);
  }

  return fetchTicketByIdFromApi(ticketId);
}

export type FetchDuplicateCandidatesOptions = {
  q?: string;
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
};

const DUPLICATE_CANDIDATE_LIMIT = 20;

function normalizeTicketPriority(value: unknown): Ticket['priority'] {
  return value === 'low' || value === 'medium' || value === 'high' || value === 'critical'
    ? value
    : null;
}

function normalizeDuplicateLocation(data: unknown): DuplicateLocation {
  const location = isRecord(data) ? data : {};
  return {
    latitude: typeof location.latitude === 'number' ? location.latitude : Number.NaN,
    longitude: typeof location.longitude === 'number' ? location.longitude : Number.NaN,
    addressText: typeof location.addressText === 'string' ? location.addressText.trim() : '',
  };
}

function optionalFiniteNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

/**
 * Keeps only the bounded candidate contract. Any extra field a server or proxy
 * adds (contact, tracking code, raw object key) is dropped here rather than
 * relying on the UI to avoid rendering it.
 */
function normalizeDuplicateCandidate(data: unknown): DuplicateCandidate | null {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    return null;
  }

  const candidate: DuplicateCandidate = {
    ticketId: data.ticketId,
    ticketNumber:
      typeof data.ticketNumber === 'string' && data.ticketNumber.trim().length > 0
        ? data.ticketNumber
        : data.ticketId,
    status: normalizeTicketStatus(data.status),
    category: typeof data.category === 'string' ? data.category : 'PENDING_CLASSIFICATION',
    priority: normalizeTicketPriority(data.priority),
    summary: typeof data.summary === 'string' ? data.summary : '',
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    location: normalizeDuplicateLocation(data.location),
    suggested: data.suggested === true,
    // The endpoint only returns rows that already satisfy the merge rules.
    mergeable: data.mergeable !== false,
  };

  const distanceMeters = optionalFiniteNumber(data.distanceMeters);
  if (distanceMeters !== undefined) {
    candidate.distanceMeters = distanceMeters;
  }
  if (typeof data.imageUrl === 'string' && data.imageUrl.trim().length > 0) {
    candidate.imageUrl = data.imageUrl;
  }
  const score = optionalFiniteNumber(data.score);
  if (score !== undefined) {
    candidate.score = score;
  }
  if (data.categoryMatch === 'same' || data.categoryMatch === 'similar') {
    candidate.categoryMatch = data.categoryMatch;
  }

  return candidate;
}

function normalizeDuplicateCandidatePage(data: unknown): DuplicateCandidatePage {
  if (!isRecord(data) || !Array.isArray(data.items)) {
    throw new Error('Unexpected duplicate candidate response shape.');
  }

  return {
    items: data.items.flatMap((item) => {
      const candidate = normalizeDuplicateCandidate(item);
      return candidate ? [candidate] : [];
    }),
    nextCursor: typeof data.nextCursor === 'string' ? data.nextCursor : null,
    limit: typeof data.limit === 'number' ? data.limit : DUPLICATE_CANDIDATE_LIMIT,
  };
}

function normalizeDuplicateComparison(data: unknown): DuplicateComparison {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    throw new Error('Unexpected duplicate comparison response shape.');
  }

  const comparison: DuplicateComparison = {
    ticketId: data.ticketId,
    ticketNumber:
      typeof data.ticketNumber === 'string' && data.ticketNumber.trim().length > 0
        ? data.ticketNumber
        : data.ticketId,
    description: typeof data.description === 'string' ? data.description : '',
    status: normalizeTicketStatus(data.status),
    category: typeof data.category === 'string' ? data.category : 'PENDING_CLASSIFICATION',
    priority: normalizeTicketPriority(data.priority),
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    location: normalizeDuplicateLocation(data.location),
  };

  if (typeof data.imageUrl === 'string' && data.imageUrl.trim().length > 0) {
    comparison.imageUrl = data.imageUrl;
  }
  const distanceMeters = optionalFiniteNumber(data.distanceMeters);
  if (distanceMeters !== undefined) {
    comparison.distanceMeters = distanceMeters;
  }

  return comparison;
}

function mockCandidateSummary(ticket: Ticket): string {
  return ticket.description.length > 240
    ? `${ticket.description.slice(0, 239).trimEnd()}…`
    : ticket.description;
}

async function fetchMockDuplicateCandidates(
  ticketId: string,
  options: FetchDuplicateCandidatesOptions,
): Promise<DuplicateCandidatePage> {
  const limit = options.limit ?? DUPLICATE_CANDIDATE_LIMIT;
  const tickets = await fetchMockTickets();
  const source = tickets.find((ticket) => ticket.ticketId === ticketId);
  if (!source) {
    throw new Error('Ticket was not found.');
  }

  const sourceCategory = effectiveTicketCategory(source);
  if (sourceCategory === null) {
    return { items: [], nextCursor: null, limit };
  }

  const matches = tickets.filter(
    (candidate) =>
      candidate.ticketId !== source.ticketId &&
      !candidate.duplicateGroupId &&
      effectiveTicketCategory(candidate) === sourceCategory &&
      ticketMatchesFetchFilters(candidate, { openOnly: true, q: options.q }),
  );
  const suggestedIds = new Set(
    (source.duplicateSuggestions ?? []).map((suggestion) => suggestion.ticketId),
  );

  const start = options.cursor ? Number.parseInt(options.cursor, 10) || 0 : 0;
  const slice = matches.slice(start, start + limit);
  const nextStart = start + limit;

  return {
    items: slice.map((candidate) => {
      const distance = distanceMetersBetween(source.location, candidate.location);
      const item: DuplicateCandidate = {
        ticketId: candidate.ticketId,
        ticketNumber: candidate.ticketNumber,
        status: candidate.status,
        category: effectiveTicketCategory(candidate) ?? candidate.category,
        priority: candidate.priority,
        summary: mockCandidateSummary(candidate),
        createdAt: candidate.createdAt,
        location: {
          latitude: candidate.location.latitude,
          longitude: candidate.location.longitude,
          addressText: candidate.location.addressText,
        },
        suggested: suggestedIds.has(candidate.ticketId),
        mergeable: true,
      };
      if (distance !== null) {
        item.distanceMeters = distance;
      }
      return item;
    }),
    nextCursor: nextStart < matches.length ? String(nextStart) : null,
    limit,
  };
}

async function fetchDuplicateCandidatesFromApi(
  ticketId: string,
  options: FetchDuplicateCandidatesOptions,
): Promise<DuplicateCandidatePage> {
  const url = new URL(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/duplicate-candidates`,
  );
  const query = options.q?.trim();
  if (query) {
    url.searchParams.set('q', query);
  }
  if (options.cursor) {
    url.searchParams.set('cursor', options.cursor);
  }
  if (options.limit) {
    url.searchParams.set('limit', String(options.limit));
  }

  const response = await fetch(url.toString(), {
    headers: {
      ...getStaffAuthHeaders(),
    },
    signal: options.signal,
  });

  if (!response.ok) {
    await throwApiError(response, 'Unable to load duplicate candidates.');
  }

  return normalizeDuplicateCandidatePage(await response.json());
}

/** Dedicated merge-candidate search for one ticket, cursor-paginated (issue #269). */
export async function fetchDuplicateCandidates(
  ticketId: string,
  options: FetchDuplicateCandidatesOptions = {},
): Promise<DuplicateCandidatePage> {
  if (config.useMockData) {
    return fetchMockDuplicateCandidates(ticketId, options);
  }

  return fetchDuplicateCandidatesFromApi(ticketId, options);
}

async function fetchMockDuplicateComparison(
  ticketId: string,
  candidateTicketId: string,
): Promise<DuplicateComparison | null> {
  const source = await fetchMockTicketById(ticketId);
  const candidate = await fetchMockTicketById(candidateTicketId);
  if (!source || !candidate) {
    return null;
  }

  const comparison: DuplicateComparison = {
    ticketId: candidate.ticketId,
    ticketNumber: candidate.ticketNumber,
    description: candidate.description,
    status: candidate.status,
    category: effectiveTicketCategory(candidate) ?? candidate.category,
    priority: candidate.priority,
    createdAt: candidate.createdAt,
    location: {
      latitude: candidate.location.latitude,
      longitude: candidate.location.longitude,
      addressText: candidate.location.addressText,
    },
  };
  const distance = distanceMetersBetween(source.location, candidate.location);
  if (distance !== null) {
    comparison.distanceMeters = distance;
  }
  return comparison;
}

async function fetchDuplicateComparisonFromApi(
  ticketId: string,
  candidateTicketId: string,
): Promise<DuplicateComparison | null> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}` +
      `/duplicate-comparison/${encodeURIComponent(candidateTicketId)}`,
    {
      headers: {
        ...getStaffAuthHeaders(),
      },
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to load the duplicate comparison.');
  }

  return normalizeDuplicateComparison(await response.json());
}

/** Bounded side-by-side comparison projection for the merge review (issue #269). */
export async function fetchDuplicateComparison(
  ticketId: string,
  candidateTicketId: string,
): Promise<DuplicateComparison | null> {
  if (config.useMockData) {
    return fetchMockDuplicateComparison(ticketId, candidateTicketId);
  }

  return fetchDuplicateComparisonFromApi(ticketId, candidateTicketId);
}

export async function fetchTicketActivity(
  ticketId: string,
  cursor?: string,
): Promise<ActivityPage> {
  if (config.useMockData) return { events: [], nextCursor: null };
  const url = new URL(`${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/activity`);
  if (cursor) url.searchParams.set('cursor', cursor);
  const response = await fetch(url, { headers: getStaffAuthHeaders() });
  if (!response.ok) await throwApiError(response, 'Unable to load ticket activity.');
  const data: unknown = await response.json();
  const events =
    isRecord(data) && Array.isArray(data.events)
      ? data.events.filter(isRecord).map((event) => ({
          eventId: String(event.eventId),
          eventType: String(event.eventType),
          occurredAt: String(event.occurredAt),
          actorDisplayName:
            typeof event.actorDisplayName === 'string' ? event.actorDisplayName : null,
          details: (isRecord(event.details)
            ? Object.fromEntries(
                Object.entries(event.details).filter(([, value]) => typeof value === 'string'),
              )
            : {}) as Record<string, string>,
          sourceReference: String(event.sourceReference),
        }))
      : [];
  return {
    events,
    nextCursor: isRecord(data) && typeof data.nextCursor === 'string' ? data.nextCursor : null,
  };
}

export async function fetchTicketComments(ticketId: string): Promise<StaffComment[]> {
  if (config.useMockData) return [];
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/comments`,
    { headers: getStaffAuthHeaders() },
  );
  if (!response.ok) await throwApiError(response, 'Unable to load ticket comments.');
  const data: unknown = await response.json();
  return Array.isArray(data) ? (data as StaffComment[]) : [];
}

export async function createTicketComment(ticketId: string, text: string): Promise<StaffComment> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/comments`,
    {
      method: 'POST',
      headers: { ...getStaffAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    },
  );
  if (!response.ok) await throwApiError(response, 'Unable to add comment.');
  return (await response.json()) as StaffComment;
}

async function updateMockTicketStatus(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket | null> {
  const ticket = await fetchMockTicketById(ticketId);

  if (!ticket) {
    return null;
  }

  const changedAt = new Date().toISOString();
  const previousHistory = ticket.statusHistory ?? [];
  return {
    ...ticket,
    status,
    updatedAt: changedAt,
    statusHistory: [
      ...previousHistory,
      {
        status,
        changedAt,
        changedBy: 'staff-mock',
        note: `Status updated to ${status}.`,
      },
    ],
  };
}

async function updateTicketStatusFromApi(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket | null> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/status`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify({ status }),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to update ticket status.');
  }

  const data: unknown = await response.json();
  const ticket = normalizeTicketFromApi(data);
  invalidateCachesForTicket(ticketId);
  return ticket;
}

export async function updateTicketStatus(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket | null> {
  if (config.useMockData) {
    const ticket = await updateMockTicketStatus(ticketId, status);
    if (ticket) {
      invalidateCachesForTicket(ticketId);
    }
    return ticket;
  }

  return updateTicketStatusFromApi(ticketId, status);
}

export type ReviewTicketCategoryInput = {
  finalCategory: string;
  categoryReviewedBy?: string;
};

async function reviewMockTicketCategory(
  ticketId: string,
  input: ReviewTicketCategoryInput,
): Promise<Ticket | null> {
  const ticket = await fetchMockTicketById(ticketId);

  if (!ticket) {
    return null;
  }

  const reviewedAt = new Date().toISOString();
  return {
    ...ticket,
    category: input.finalCategory,
    updatedAt: reviewedAt,
    ai: {
      ...ticket.ai,
      finalCategory: input.finalCategory,
      categoryReviewedBy: input.categoryReviewedBy,
      categoryReviewedAt: reviewedAt,
    },
  };
}

async function reviewTicketCategoryFromApi(
  ticketId: string,
  input: ReviewTicketCategoryInput,
): Promise<Ticket | null> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/category`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(input),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to save category review.');
  }

  const data: unknown = await response.json();
  const ticket = normalizeTicketFromApi(data);
  invalidateCachesForTicket(ticketId);
  return ticket;
}

export async function reviewTicketCategory(
  ticketId: string,
  input: ReviewTicketCategoryInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    const ticket = await reviewMockTicketCategory(ticketId, input);
    if (ticket) {
      invalidateCachesForTicket(ticketId);
    }
    return ticket;
  }

  return reviewTicketCategoryFromApi(ticketId, input);
}

export type MergeDuplicateTicketsInput = {
  canonicalTicketId: string;
  duplicateTicketIds: string[];
  mergedBy?: string;
};

async function mergeMockDuplicateTickets(
  input: MergeDuplicateTicketsInput,
): Promise<Ticket | null> {
  const tickets = await fetchMockTickets();
  const canonical = tickets.find((ticket) => ticket.ticketId === input.canonicalTicketId);
  if (!canonical) {
    return null;
  }

  if (input.duplicateTicketIds.includes(input.canonicalTicketId)) {
    throw new Error('The main ticket cannot also appear in the duplicate ticket list.');
  }

  // Mirror the backend validation so mock mode is a faithful test of the action.
  const canonicalCategory = effectiveTicketCategory(canonical);
  if (canonicalCategory === null) {
    throw new Error(
      'The main ticket has no reviewed or AI-suggested category yet. ' +
        'Merge is only allowed between classified tickets.',
    );
  }

  const duplicates: Ticket[] = [];
  for (const duplicateId of input.duplicateTicketIds) {
    const duplicate = tickets.find((ticket) => ticket.ticketId === duplicateId);
    if (!duplicate) {
      return null;
    }
    if (duplicate.duplicateGroupId) {
      throw new Error(`Ticket ${duplicateId} already belongs to a duplicate group.`);
    }
    const duplicateCategory = effectiveTicketCategory(duplicate);
    if (duplicateCategory === null || duplicateCategory !== canonicalCategory) {
      throw new Error('All merged tickets must share the same category as the main ticket.');
    }
    duplicates.push(duplicate);
  }

  let group: TicketDuplicateReference;
  if (canonical.duplicateGroupId) {
    const existing = buildMockGroupReference(tickets, canonical.duplicateGroupId);
    if (existing.canonicalTicketId !== canonical.ticketId) {
      throw new Error(
        `This ticket is already grouped under main ticket ${existing.canonicalTicketId}. ` +
          'Merge additional duplicates from the main ticket instead.',
      );
    }
    group = {
      ...existing,
      ticketIds: [
        ...(existing.ticketIds ?? []),
        ...input.duplicateTicketIds.filter((id) => !existing.ticketIds?.includes(id)),
      ],
    };
  } else {
    group = {
      duplicateGroupId: `dup_mock_${Date.now()}`,
      ticketIds: [input.canonicalTicketId, ...input.duplicateTicketIds],
      canonicalTicketId: input.canonicalTicketId,
    };
  }

  // Persist for the session so every member reflects the group on re-read.
  mockMergeGroups.set(group.duplicateGroupId, group);
  for (const memberId of group.ticketIds ?? []) {
    mockTicketGroupIds.set(memberId, group.duplicateGroupId);
  }

  return {
    ...canonical,
    duplicateGroupId: group.duplicateGroupId,
    updatedAt: new Date().toISOString(),
    duplicateGroup: group,
  };
}

async function mergeDuplicateTicketsFromApi(
  input: MergeDuplicateTicketsInput,
): Promise<Ticket | null> {
  const response = await fetch(`${config.apiBaseUrl}/v1/tickets/merge`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getStaffAuthHeaders(),
    },
    body: JSON.stringify(input),
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to merge duplicate tickets.');
  }

  const data: unknown = await response.json();
  const ticket = normalizeTicketFromApi(data);
  invalidateTicketListCache();
  return ticket;
}

export async function mergeDuplicateTickets(
  input: MergeDuplicateTicketsInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    const ticket = await mergeMockDuplicateTickets(input);
    if (ticket) {
      invalidateTicketListCache();
    }
    return ticket;
  }

  return mergeDuplicateTicketsFromApi(input);
}

export type AssignTicketDepartmentInput = {
  departmentId: string;
  updatedBy?: string;
};

async function assignMockTicketDepartment(
  ticketId: string,
  input: AssignTicketDepartmentInput,
): Promise<Ticket | null> {
  const ticket = await fetchMockTicketById(ticketId);

  if (!ticket) {
    return null;
  }

  if (!(input.departmentId in DEPARTMENT_NAMES)) {
    throw new Error('departmentId: Department is not in the seeded catalog.');
  }

  const updatedAt = new Date().toISOString();
  const departmentName = DEPARTMENT_NAMES[input.departmentId];

  return {
    ...ticket,
    departmentId: input.departmentId,
    departmentName,
    department: {
      departmentId: input.departmentId,
      name: departmentName,
    },
    updatedAt,
    updatedBy: input.updatedBy ?? ticket.updatedBy ?? null,
    ai: {
      ...ticket.ai,
      // Preserve the automatic suggestion when staff overrides the assignment.
      suggestedDepartmentId: ticket.ai?.suggestedDepartmentId,
    },
  };
}

async function assignTicketDepartmentFromApi(
  ticketId: string,
  input: AssignTicketDepartmentInput,
): Promise<Ticket | null> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/department`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(input),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to update ticket department.');
  }

  const data: unknown = await response.json();
  const ticket = normalizeTicketFromApi(data);
  invalidateCachesForTicket(ticketId);
  return ticket;
}

export async function assignTicketDepartment(
  ticketId: string,
  input: AssignTicketDepartmentInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    const ticket = await assignMockTicketDepartment(ticketId, input);
    if (ticket) {
      invalidateCachesForTicket(ticketId);
    }
    return ticket;
  }

  return assignTicketDepartmentFromApi(ticketId, input);
}

export type UpdateTicketPublicContentInput = {
  publicStatus: PublicTicketStatus;
  publicDescription: string;
  publicLocationLabel: string;
  approveOriginalPhoto?: boolean;
  clearPublicPhoto?: boolean;
};

async function updateMockTicketPublicContent(
  ticketId: string,
  input: UpdateTicketPublicContentInput,
): Promise<Ticket | null> {
  const ticket = await fetchMockTicketById(ticketId);
  if (!ticket) {
    return null;
  }

  const publishedAt =
    input.publicStatus === 'PUBLISHED'
      ? (ticket.public?.publishedAt ?? new Date().toISOString())
      : (ticket.public?.publishedAt ?? null);

  let imageObjectKey = ticket.public?.imageObjectKey ?? null;
  if (input.clearPublicPhoto) {
    imageObjectKey = null;
  } else if (input.approveOriginalPhoto) {
    imageObjectKey = ticket.imageObjectKey;
  }

  return {
    ...ticket,
    updatedAt: new Date().toISOString(),
    public: {
      status: input.publicStatus,
      description: input.publicDescription.trim() || null,
      locationLabel: input.publicLocationLabel.trim() || null,
      imageObjectKey,
      publishedAt,
    },
  };
}

async function updateTicketPublicContentFromApi(
  ticketId: string,
  input: UpdateTicketPublicContentInput,
): Promise<Ticket | null> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/public`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(input),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    await throwApiError(response, 'Unable to update public content.');
  }

  const data: unknown = await response.json();
  const ticket = normalizeTicketFromApi(data);
  invalidateCachesForTicket(ticketId);
  return ticket;
}

export async function updateTicketPublicContent(
  ticketId: string,
  input: UpdateTicketPublicContentInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    const ticket = await updateMockTicketPublicContent(ticketId, input);
    if (ticket) {
      invalidateCachesForTicket(ticketId);
    }
    return ticket;
  }

  return updateTicketPublicContentFromApi(ticketId, input);
}

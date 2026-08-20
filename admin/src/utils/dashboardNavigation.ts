/** Safe dashboard filter/search-param helpers. Never put private data in URLs. */

const SAFE_STRING_KEYS = [
  'urgency',
  'openOnly',
  'status',
  'category',
  'departmentId',
  'slaState',
  'assignmentState',
  'ticketIds',
  'workerId',
  'teamId',
  'contentSafetyStatus',
  'focusTicket',
] as const;

const SAFE_NUMBER_KEYS = ['south', 'west', 'north', 'east', 'zoom'] as const;

export type DashboardNavigationFilters = {
  urgency?: string;
  openOnly?: boolean;
  status?: string;
  category?: string;
  departmentId?: string;
  slaState?: string;
  assignmentState?: string;
  ticketIds?: string[];
  workerId?: string;
  teamId?: string;
  contentSafetyStatus?: string;
  focusTicket?: string;
  south?: number;
  west?: number;
  north?: number;
  east?: number;
  zoom?: number;
};

function isSafeId(value: string): boolean {
  return /^[A-Za-z0-9._:-]{1,80}$/.test(value);
}

function parseNumber(value: string | null): number | undefined {
  if (value == null || value.trim() === '') {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

export function parseDashboardSearchParams(params: URLSearchParams): DashboardNavigationFilters {
  const filters: DashboardNavigationFilters = {};
  const urgency = params.get('urgency')?.trim();
  if (urgency && /^[a-z]+(?:,[a-z]+)*$/.test(urgency)) {
    filters.urgency = urgency;
  }
  if (params.get('openOnly') === 'true') {
    filters.openOnly = true;
  }
  const status = params.get('status')?.trim();
  if (status && /^[A-Z_]+$/.test(status)) {
    filters.status = status;
  }
  const category = params.get('category')?.trim();
  if (category && /^[a-z0-9_]+$/.test(category)) {
    filters.category = category;
  }
  const departmentId = params.get('departmentId')?.trim();
  if (departmentId && isSafeId(departmentId)) {
    filters.departmentId = departmentId;
  }
  const slaState = params.get('slaState')?.trim();
  if (slaState && /^[a-z_]+$/.test(slaState)) {
    filters.slaState = slaState;
  }
  const assignmentState = params.get('assignmentState')?.trim();
  if (assignmentState === 'assigned' || assignmentState === 'unassigned') {
    filters.assignmentState = assignmentState;
  }
  const ticketIds = params.get('ticketIds')?.split(',') ?? [];
  const safeTicketIds = ticketIds.map((item) => item.trim()).filter(isSafeId);
  if (safeTicketIds.length > 0) {
    filters.ticketIds = safeTicketIds.slice(0, 20);
  }
  const workerId = params.get('workerId')?.trim();
  if (workerId && isSafeId(workerId)) {
    filters.workerId = workerId;
  }
  const teamId = params.get('teamId')?.trim();
  if (teamId && isSafeId(teamId)) {
    filters.teamId = teamId;
  }
  const contentSafetyStatus = params.get('contentSafetyStatus')?.trim();
  if (contentSafetyStatus && /^[a-z_]+$/.test(contentSafetyStatus)) {
    filters.contentSafetyStatus = contentSafetyStatus;
  }
  const focusTicket = params.get('focusTicket')?.trim();
  if (focusTicket && isSafeId(focusTicket)) {
    filters.focusTicket = focusTicket;
  }
  for (const key of SAFE_NUMBER_KEYS) {
    const parsed = parseNumber(params.get(key));
    if (parsed !== undefined) {
      filters[key] = parsed;
    }
  }
  return filters;
}

export function serializeDashboardSearchParams(
  filters: DashboardNavigationFilters,
): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.urgency) {
    params.set('urgency', filters.urgency);
  }
  if (filters.openOnly) {
    params.set('openOnly', 'true');
  }
  if (filters.status && filters.status !== 'ALL') {
    params.set('status', filters.status);
  }
  if (filters.category && filters.category !== 'ALL') {
    params.set('category', filters.category);
  }
  if (filters.departmentId && filters.departmentId !== 'ALL') {
    params.set('departmentId', filters.departmentId);
  }
  if (filters.slaState && filters.slaState !== 'ALL') {
    params.set('slaState', filters.slaState);
  }
  if (filters.assignmentState && filters.assignmentState !== 'ALL') {
    params.set('assignmentState', filters.assignmentState);
  }
  if (filters.ticketIds && filters.ticketIds.length > 0) {
    params.set('ticketIds', filters.ticketIds.filter(isSafeId).slice(0, 20).join(','));
  }
  if (filters.workerId && isSafeId(filters.workerId)) {
    params.set('workerId', filters.workerId);
  }
  if (filters.teamId && isSafeId(filters.teamId)) {
    params.set('teamId', filters.teamId);
  }
  if (filters.contentSafetyStatus && filters.contentSafetyStatus !== 'ALL') {
    params.set('contentSafetyStatus', filters.contentSafetyStatus);
  }
  if (filters.focusTicket && isSafeId(filters.focusTicket)) {
    params.set('focusTicket', filters.focusTicket);
  }
  for (const key of SAFE_NUMBER_KEYS) {
    const value = filters[key];
    if (typeof value === 'number' && Number.isFinite(value)) {
      params.set(key, String(value));
    }
  }
  return params;
}

export function buildTicketListPath(filters: DashboardNavigationFilters): string {
  const params = serializeDashboardSearchParams({
    urgency: filters.urgency,
    openOnly: filters.openOnly,
    status: filters.status,
    category: filters.category,
    departmentId: filters.departmentId,
    slaState: filters.slaState,
    assignmentState: filters.assignmentState,
    ticketIds: filters.ticketIds,
    workerId: filters.workerId,
    teamId: filters.teamId,
    contentSafetyStatus: filters.contentSafetyStatus,
    focusTicket: filters.focusTicket,
  });
  const query = params.toString();
  return query ? `/?${query}` : '/';
}

export function buildMapPath(filters: DashboardNavigationFilters): string {
  const params = serializeDashboardSearchParams({
    urgency: filters.urgency,
    openOnly: filters.openOnly,
    status: filters.status,
    category: filters.category,
    departmentId: filters.departmentId,
    ticketIds: filters.ticketIds,
    south: filters.south,
    west: filters.west,
    north: filters.north,
    east: filters.east,
    zoom: filters.zoom,
  });
  const query = params.toString();
  return query ? `/map?${query}` : '/map';
}

export function buildWorkforcePath(
  filters: Pick<DashboardNavigationFilters, 'workerId' | 'teamId'>,
): string {
  const params = serializeDashboardSearchParams({
    workerId: filters.workerId,
    teamId: filters.teamId,
  });
  const query = params.toString();
  return query ? `/workforce?${query}` : '/workforce';
}

export function buildTicketDetailPath(ticketId: string): string {
  return isSafeId(ticketId) ? `/tickets/${ticketId}` : '/';
}

export function assistantFiltersFromApplied(
  applied: Record<string, string>,
): DashboardNavigationFilters {
  const allowed = new Set<string>(SAFE_STRING_KEYS);
  const next: DashboardNavigationFilters = {};
  if (applied.urgency && allowed.has('urgency')) {
    next.urgency = applied.urgency;
  }
  if (applied.openOnly === 'true') {
    next.openOnly = true;
  }
  if (applied.status) {
    next.status = applied.status;
  }
  if (applied.category) {
    next.category = applied.category;
  }
  if (applied.departmentId) {
    next.departmentId = applied.departmentId;
  }
  return next;
}

export function hasMapBounds(filters: DashboardNavigationFilters): boolean {
  return (
    typeof filters.south === 'number' &&
    typeof filters.west === 'number' &&
    typeof filters.north === 'number' &&
    typeof filters.east === 'number'
  );
}

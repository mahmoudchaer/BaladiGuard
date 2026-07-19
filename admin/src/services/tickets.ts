import type {
  AiProcessingStatus,
  Ticket,
  TicketAiFields,
  TicketDuplicateReference,
  TicketLocation,
  TicketStatus,
} from '@/types/ticket';
import mockTickets from '../../../mock_tickets.json';
import { config } from '@/services/config';
import { effectiveTicketCategory } from '@/utils/ticketCategory';

const MOCK_LOAD_DELAY_MS = 350;

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

async function fetchMockTickets(): Promise<Ticket[]> {
  await new Promise((resolve) => setTimeout(resolve, MOCK_LOAD_DELAY_MS));

  if (!isTicketArray(mockTickets)) {
    throw new Error('Invalid mock ticket fixtures.');
  }

  return [...mockTickets]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .map((ticket) => applyMockMergeState(ticket));
}

async function fetchTicketsFromApi(): Promise<Ticket[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/tickets`);

  if (!response.ok) {
    const message = await readApiErrorMessage(response, 'Unable to load tickets from the server.');
    throw new Error(message);
  }

  const data: unknown = await response.json();

  if (!isTicketArray(data)) {
    throw new Error('Unexpected ticket list response shape.');
  }

  return data.map((ticket) => normalizeTicketFromApi(ticket));
}

export async function fetchTickets(): Promise<Ticket[]> {
  if (config.useMockData) {
    return fetchMockTickets();
  }

  return fetchTicketsFromApi();
}

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
    urgencyReason: typeof data.urgencyReason === 'string' ? data.urgencyReason : undefined,
    summary: typeof data.summary === 'string' ? data.summary : undefined,
  };

  const hasAiData = Object.values(ai).some((value) => value !== undefined);
  return hasAiData ? ai : undefined;
}

function normalizeTicketLocation(data: unknown): TicketLocation {
  if (!isRecord(data)) {
    throw new Error('Unexpected ticket location response shape.');
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

  if (!hasValidLatitude || !hasValidLongitude || normalizedAddress.length < 3 || !hasValidSource) {
    throw new Error('Unexpected ticket location response shape.');
  }

  return {
    latitude,
    longitude,
    addressText: normalizedAddress,
    source,
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
    status:
      data.status === 'SUBMITTED' ||
      data.status === 'UNDER_REVIEW' ||
      data.status === 'ASSIGNED' ||
      data.status === 'IN_PROGRESS' ||
      data.status === 'RESOLVED' ||
      data.status === 'CLOSED'
        ? data.status
        : 'SUBMITTED',
    category: typeof data.category === 'string' ? data.category : 'PENDING_CLASSIFICATION',
    priority:
      data.priority === 'low' || data.priority === 'medium' || data.priority === 'high'
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
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    updatedAt: typeof data.updatedAt === 'string' ? data.updatedAt : null,
    ai: normalizeTicketAiFields(data.ai),
  };
}

async function fetchTicketByIdFromApi(ticketId: string): Promise<Ticket | null> {
  const response = await fetch(`${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const message = await readApiErrorMessage(response, 'Unable to load ticket from the server.');
    throw new Error(message);
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

async function updateMockTicketStatus(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket | null> {
  const ticket = await fetchMockTicketById(ticketId);

  if (!ticket) {
    return null;
  }

  return {
    ...ticket,
    status,
    updatedAt: new Date().toISOString(),
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
      },
      body: JSON.stringify({ status }),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const message = await readApiErrorMessage(response, 'Unable to update ticket status.');
    throw new Error(message);
  }

  const data: unknown = await response.json();
  return normalizeTicketFromApi(data);
}

export async function updateTicketStatus(
  ticketId: string,
  status: TicketStatus,
): Promise<Ticket | null> {
  if (config.useMockData) {
    return updateMockTicketStatus(ticketId, status);
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
      },
      body: JSON.stringify(input),
    },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const message = await readApiErrorMessage(response, 'Unable to save category review.');
    throw new Error(message);
  }

  const data: unknown = await response.json();
  return normalizeTicketFromApi(data);
}

export async function reviewTicketCategory(
  ticketId: string,
  input: ReviewTicketCategoryInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    return reviewMockTicketCategory(ticketId, input);
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
    },
    body: JSON.stringify(input),
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const message = await readApiErrorMessage(response, 'Unable to merge duplicate tickets.');
    throw new Error(message);
  }

  const data: unknown = await response.json();
  return normalizeTicketFromApi(data);
}

export async function mergeDuplicateTickets(
  input: MergeDuplicateTicketsInput,
): Promise<Ticket | null> {
  if (config.useMockData) {
    return mergeMockDuplicateTickets(input);
  }

  return mergeDuplicateTicketsFromApi(input);
}

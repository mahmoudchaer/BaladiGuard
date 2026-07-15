import type { Ticket, TicketStatus } from '@/types/ticket';
import mockTickets from '../../../mock_tickets.json';
import { config } from '@/services/config';

const MOCK_LOAD_DELAY_MS = 350;

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

  return [...mockTickets].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );
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

  return data;
}

export async function fetchTickets(): Promise<Ticket[]> {
  if (config.useMockData) {
    return fetchMockTickets();
  }

  return fetchTicketsFromApi();
}

async function fetchMockTicketById(ticketId: string): Promise<Ticket | null> {
  const tickets = await fetchMockTickets();
  return tickets.find((ticket) => ticket.ticketId === ticketId) ?? null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

function normalizeTicketFromApi(data: unknown): Ticket {
  if (!isRecord(data) || typeof data.ticketId !== 'string') {
    throw new Error('Unexpected ticket response shape.');
  }

  const location = isRecord(data.location) ? data.location : {};
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
    location: {
      latitude: typeof location.latitude === 'number' ? location.latitude : 0,
      longitude: typeof location.longitude === 'number' ? location.longitude : 0,
      addressText: typeof location.addressText === 'string' ? location.addressText : 'Not provided',
      source:
        location.source === 'GPS' ||
        location.source === 'MANUAL' ||
        location.source === 'PLACEHOLDER'
          ? location.source
          : 'PLACEHOLDER',
    },
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
    createdAt: typeof data.createdAt === 'string' ? data.createdAt : new Date().toISOString(),
    updatedAt: typeof data.updatedAt === 'string' ? data.updatedAt : null,
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

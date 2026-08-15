import { config } from '@/services/config';
import { getStaffAuthHeaders } from '@/services/auth';
import type { WorkOrder, WorkOrderEvidence, WorkOrderList } from '@/types/workOrder';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

async function throwApiError(response: Response, fallbackMessage: string): Promise<never> {
  const body = await response.json().catch(() => null);
  const error = isRecord(body) && isRecord(body.error) ? body.error : null;
  const message = error && typeof error.message === 'string' ? error.message : fallbackMessage;
  throw new Error(message);
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null;
}

function normalizeEvidence(data: unknown): WorkOrderEvidence | null {
  if (
    !isRecord(data) ||
    typeof data.evidenceId !== 'string' ||
    typeof data.ticketId !== 'string' ||
    typeof data.workOrderId !== 'string' ||
    (data.kind !== 'BEFORE' && data.kind !== 'AFTER' && data.kind !== 'ORIGINAL_REPORT')
  ) {
    return null;
  }
  return {
    evidenceId: data.evidenceId,
    ticketId: data.ticketId,
    workOrderId: data.workOrderId,
    kind: data.kind,
    objectKey: asString(data.objectKey) ?? '',
    contentType: asString(data.contentType) ?? '',
    uploadedBy: asString(data.uploadedBy) ?? '',
    createdAt: asString(data.createdAt) ?? '',
    source: data.source === 'TICKET_ORIGINAL' ? 'TICKET_ORIGINAL' : 'UPLOAD',
    photoUrl: asString(data.photoUrl),
  };
}

function normalizeWorkOrder(data: unknown): WorkOrder {
  if (
    !isRecord(data) ||
    typeof data.workOrderId !== 'string' ||
    typeof data.ticketId !== 'string'
  ) {
    throw new Error('Unexpected work-order response shape.');
  }
  return {
    workOrderId: data.workOrderId,
    ticketId: data.ticketId,
    municipalityId: asString(data.municipalityId) ?? '',
    departmentId: asString(data.departmentId) ?? '',
    state: (asString(data.state) ?? 'QUEUED') as WorkOrder['state'],
    summary: asString(data.summary) ?? '',
    assignedWorkerId: asString(data.assignedWorkerId),
    assignedTeamId: asString(data.assignedTeamId),
    createdAt: asString(data.createdAt) ?? '',
    createdBy: asString(data.createdBy) ?? '',
    updatedAt: asString(data.updatedAt) ?? '',
    updatedBy: asString(data.updatedBy) ?? '',
    startedAt: asString(data.startedAt),
    startedBy: asString(data.startedBy),
    completedAt: asString(data.completedAt),
    completedBy: asString(data.completedBy),
    cancelledAt: asString(data.cancelledAt),
    cancelledBy: asString(data.cancelledBy),
    cancelReasonCode: asString(data.cancelReasonCode),
    completionNote: asString(data.completionNote),
    cancelNote: asString(data.cancelNote),
    ticketStatus: asString(data.ticketStatus),
    created: data.created === true,
    evidence: Array.isArray(data.evidence)
      ? data.evidence
          .map(normalizeEvidence)
          .filter((item): item is WorkOrderEvidence => item !== null)
      : [],
    afterImageCount:
      typeof data.afterImageCount === 'number'
        ? data.afterImageCount
        : Array.isArray(data.evidence)
          ? data.evidence.filter((item) => isRecord(item) && item.kind === 'AFTER').length
          : 0,
  };
}

async function readWorkOrder(response: Response, fallback: string): Promise<WorkOrder> {
  if (!response.ok) {
    await throwApiError(response, fallback);
  }
  return normalizeWorkOrder(await response.json());
}

export async function listTicketWorkOrders(ticketId: string): Promise<WorkOrderList> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/work-orders`,
    { headers: { ...getStaffAuthHeaders() } },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to load work orders.');
  }
  const data: unknown = await response.json();
  if (!isRecord(data) || !Array.isArray(data.items)) {
    throw new Error('Unexpected work-order list response.');
  }
  return {
    items: data.items.map(normalizeWorkOrder),
    activeWorkOrderId: asString(data.activeWorkOrderId),
  };
}

export async function createTicketWorkOrder(
  ticketId: string,
  input: { summary?: string; workerId?: string; teamId?: string } = {},
): Promise<WorkOrder> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/tickets/${encodeURIComponent(ticketId)}/work-orders`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(input),
    },
  );
  return readWorkOrder(response, 'Unable to create a work order.');
}

export async function assignWorkOrder(
  workOrderId: string,
  input: { workerId?: string; teamId?: string; clear?: boolean },
): Promise<WorkOrder> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/work-orders/${encodeURIComponent(workOrderId)}/assign`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(input),
    },
  );
  return readWorkOrder(response, 'Unable to assign the work order.');
}

export async function startWorkOrder(workOrderId: string): Promise<WorkOrder> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/work-orders/${encodeURIComponent(workOrderId)}/start`,
    {
      method: 'POST',
      headers: { ...getStaffAuthHeaders() },
    },
  );
  return readWorkOrder(response, 'Unable to start the work order.');
}

export async function uploadWorkOrderEvidence(
  workOrderId: string,
  kind: 'BEFORE' | 'AFTER',
  file: File,
): Promise<WorkOrderEvidence> {
  const body = new FormData();
  body.append('file', file);
  const response = await fetch(
    `${config.apiBaseUrl}/v1/work-orders/${encodeURIComponent(workOrderId)}/evidence?kind=${kind}`,
    {
      method: 'POST',
      headers: { ...getStaffAuthHeaders() },
      body,
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to upload maintenance evidence.');
  }
  const evidence = normalizeEvidence(await response.json());
  if (!evidence) {
    throw new Error('Unexpected evidence response shape.');
  }
  return evidence;
}

export async function completeWorkOrder(workOrderId: string, note?: string): Promise<WorkOrder> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/work-orders/${encodeURIComponent(workOrderId)}/complete`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify({ note }),
    },
  );
  return readWorkOrder(response, 'Unable to complete the work order.');
}

export async function cancelWorkOrder(
  workOrderId: string,
  reasonCode: string,
  note?: string,
): Promise<WorkOrder> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/work-orders/${encodeURIComponent(workOrderId)}/cancel`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify({ reasonCode, note }),
    },
  );
  return readWorkOrder(response, 'Unable to cancel the work order.');
}

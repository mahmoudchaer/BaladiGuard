import { getStaffAuthHeaders } from '@/services/auth';
import { config } from '@/services/config';
import { throwApiError } from '@/services/tickets';
import type { StaffAssistantResponse } from '@/types/staffAssistant';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

export function parseStaffAssistantResponse(value: unknown): StaffAssistantResponse | null {
  if (!isRecord(value)) {
    return null;
  }
  if (
    (value.intent !== 'high_priority_summary' &&
      value.intent !== 'repeated_area_summary' &&
      value.intent !== 'unsupported') ||
    typeof value.asOf !== 'string' ||
    typeof value.message !== 'string' ||
    typeof value.count !== 'number'
  ) {
    return null;
  }
  return {
    intent: value.intent,
    asOf: value.asOf,
    message: value.message,
    count: value.count,
    categories: isRecord(value.categories) ? (value.categories as Record<string, number>) : {},
    statuses: isRecord(value.statuses) ? (value.statuses as Record<string, number>) : {},
    departments: isRecord(value.departments) ? (value.departments as Record<string, number>) : {},
    areas: isRecord(value.areas) ? (value.areas as Record<string, number>) : {},
    areaClusters: Array.isArray(value.areaClusters)
      ? (value.areaClusters as StaffAssistantResponse['areaClusters'])
      : [],
    areaClusterTotal: typeof value.areaClusterTotal === 'number' ? value.areaClusterTotal : 0,
    areaClustersTruncated: value.areaClustersTruncated === true,
    unlocatedCount: typeof value.unlocatedCount === 'number' ? value.unlocatedCount : 0,
    incompleteCount: typeof value.incompleteCount === 'number' ? value.incompleteCount : 0,
    tickets: Array.isArray(value.tickets) ? (value.tickets as StaffAssistantResponse['tickets']) : [],
    appliedFilters: isRecord(value.appliedFilters)
      ? (value.appliedFilters as Record<string, string>)
      : {},
  };
}

export async function queryStaffAssistant(
  question: string,
  signal?: AbortSignal,
): Promise<StaffAssistantResponse> {
  const response = await fetch(`${config.apiBaseUrl}/v1/staff-assistant/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getStaffAuthHeaders(),
    },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to ask the staff assistant.');
  }
  const parsed = parseStaffAssistantResponse(await response.json());
  if (!parsed) {
    throw new Error('The assistant returned an unexpected response.');
  }
  return parsed;
}

import { getStaffAuthHeaders } from '@/services/auth';
import { config } from '@/services/config';
import { throwApiError } from '@/services/tickets';
import type { StaffSearchResponse } from '@/types/staffSearch';

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

export function parseStaffSearchResponse(value: unknown): StaffSearchResponse | null {
  if (!isRecord(value) || typeof value.asOf !== 'string' || typeof value.query !== 'string') {
    return null;
  }
  return {
    asOf: value.asOf,
    query: value.query,
    tickets: Array.isArray(value.tickets) ? (value.tickets as StaffSearchResponse['tickets']) : [],
    workers: Array.isArray(value.workers) ? (value.workers as StaffSearchResponse['workers']) : [],
    teams: Array.isArray(value.teams) ? (value.teams as StaffSearchResponse['teams']) : [],
    workOrders: Array.isArray(value.workOrders)
      ? (value.workOrders as StaffSearchResponse['workOrders'])
      : [],
    ticketsTruncated: value.ticketsTruncated === true,
    workersTruncated: value.workersTruncated === true,
    teamsTruncated: value.teamsTruncated === true,
    workOrdersTruncated: value.workOrdersTruncated === true,
    scanTruncated: value.scanTruncated === true,
    workforceScanTruncated: value.workforceScanTruncated === true,
    workOrderScanTruncated: value.workOrderScanTruncated === true,
    partialFailures: Array.isArray(value.partialFailures)
      ? value.partialFailures.filter((item): item is string => typeof item === 'string')
      : [],
    limits: isRecord(value.limits) ? (value.limits as Record<string, number>) : {},
  };
}

export async function searchStaffRecords(
  query: string,
  signal?: AbortSignal,
): Promise<StaffSearchResponse> {
  const url = new URL(`${config.apiBaseUrl}/v1/staff-search`);
  url.searchParams.set('q', query);
  const response = await fetch(url, {
    headers: {
      ...getStaffAuthHeaders(),
    },
    signal,
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to search operational records.');
  }
  const parsed = parseStaffSearchResponse(await response.json());
  if (!parsed) {
    throw new Error('Search returned an unexpected response.');
  }
  return parsed;
}

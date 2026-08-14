import { getStaffAuthHeaders } from '@/services/auth';
import { config } from '@/services/config';
import type { WorkforceTeam, WorkforceWorker, WorkloadSnapshot } from '@/types/workforce';

export type UpsertWorkerInput = {
  municipalityId?: string;
  displayName?: string;
  departmentIds?: string[];
  teamIds?: string[];
};

export type UpsertTeamInput = {
  municipalityId?: string;
  displayName?: string;
  departmentIds?: string[];
  workerIds?: string[];
};

async function throwApiError(response: Response, fallback: string): Promise<never> {
  let message = fallback;
  try {
    const payload = (await response.json()) as { error?: { message?: string } };
    if (typeof payload.error?.message === 'string' && payload.error.message.trim()) {
      message = payload.error.message;
    }
  } catch {
    /* keep fallback */
  }
  throw new Error(message);
}

function authHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...getStaffAuthHeaders(),
  };
}

export async function listWorkers(municipalityId?: string | null): Promise<WorkforceWorker[]> {
  const url = new URL(`${config.apiBaseUrl}/v1/workforce/workers`);
  if (municipalityId) {
    url.searchParams.set('municipalityId', municipalityId);
  }
  const response = await fetch(url, { headers: getStaffAuthHeaders() });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load workers.');
  }
  return (await response.json()) as WorkforceWorker[];
}

export async function listTeams(municipalityId?: string | null): Promise<WorkforceTeam[]> {
  const url = new URL(`${config.apiBaseUrl}/v1/workforce/teams`);
  if (municipalityId) {
    url.searchParams.set('municipalityId', municipalityId);
  }
  const response = await fetch(url, { headers: getStaffAuthHeaders() });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load teams.');
  }
  return (await response.json()) as WorkforceTeam[];
}

export async function createWorker(input: UpsertWorkerInput): Promise<WorkforceWorker> {
  const response = await fetch(`${config.apiBaseUrl}/v1/workforce/workers`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to create worker.');
  }
  return (await response.json()) as WorkforceWorker;
}

export async function updateWorker(
  workerId: string,
  input: UpsertWorkerInput,
): Promise<WorkforceWorker> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/workforce/workers/${encodeURIComponent(workerId)}`,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to update worker.');
  }
  return (await response.json()) as WorkforceWorker;
}

export async function setWorkerActive(workerId: string, active: boolean): Promise<WorkforceWorker> {
  const action = active ? 'reactivate' : 'deactivate';
  const response = await fetch(
    `${config.apiBaseUrl}/v1/workforce/workers/${encodeURIComponent(workerId)}/${action}`,
    { method: 'POST', headers: getStaffAuthHeaders() },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to update worker status.');
  }
  return (await response.json()) as WorkforceWorker;
}

export async function createTeam(input: UpsertTeamInput): Promise<WorkforceTeam> {
  const response = await fetch(`${config.apiBaseUrl}/v1/workforce/teams`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to create team.');
  }
  return (await response.json()) as WorkforceTeam;
}

export async function updateTeam(teamId: string, input: UpsertTeamInput): Promise<WorkforceTeam> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/workforce/teams/${encodeURIComponent(teamId)}`,
    {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(input),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to update team.');
  }
  return (await response.json()) as WorkforceTeam;
}

export async function setTeamActive(teamId: string, active: boolean): Promise<WorkforceTeam> {
  const action = active ? 'reactivate' : 'deactivate';
  const response = await fetch(
    `${config.apiBaseUrl}/v1/workforce/teams/${encodeURIComponent(teamId)}/${action}`,
    { method: 'POST', headers: getStaffAuthHeaders() },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to update team status.');
  }
  return (await response.json()) as WorkforceTeam;
}

export async function fetchWorkload(municipalityId?: string | null): Promise<WorkloadSnapshot> {
  const url = new URL(`${config.apiBaseUrl}/v1/workforce/workload`);
  if (municipalityId) {
    url.searchParams.set('municipalityId', municipalityId);
  }
  const response = await fetch(url, { headers: getStaffAuthHeaders() });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load workload.');
  }
  return (await response.json()) as WorkloadSnapshot;
}

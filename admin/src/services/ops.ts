import { config } from '@/services/config';
import { clearStoredStaffSession, getStaffAuthHeaders } from '@/services/auth';

export type OpsTimeRange = '1h' | '6h' | '24h' | '7d';

export type WorkerKind = 'ai' | 'redaction' | 'notifications' | 'whatsapp' | 'moderation';

export type OpsOverview = {
  generatedAt: string;
  telemetrySource: 'cloudwatch' | 'application' | 'mixed';
  telemetryWarning: string | null;
  health: {
    ready: boolean;
    live: boolean;
    database: string;
    configuration: string;
    version: string;
    env: string;
  };
  traffic: {
    requests: number;
    errors: number;
    errorRate: number;
    latencyMs: number;
    throttles: number;
    authFailures: number;
  };
  workers: Array<{
    kind: WorkerKind;
    label: string;
    deployed: boolean;
    pending: number;
    running: number;
    succeeded: number;
    deadLettered: number;
    oldestAgeSeconds: number | null;
    retries: number;
    lastErrorCode: string | null;
  }>;
  alerts: OpsAlert[];
  product: OpsProduct;
  backup: { status: string; detail: string; source: string };
  cloudwatchDashboardUrl: string | null;
  municipalityManagement: { available: boolean; issue: string; label: string };
};

export type OpsAlert = {
  alarmName: string;
  metricName: string;
  state: string;
  severity: string;
  reason: string;
  runbookUrl: string;
  awsConsoleUrl: string | null;
  ackStatus: 'open' | 'acknowledged';
  ackBy: string | null;
  ackAt: string | null;
  ackNote: string | null;
  owner: string;
};

export type OpsProduct = {
  reportsSubmitted: number;
  reportsFailed: number;
  ticketsOpen: number;
  ticketsResolved: number;
  ticketsClosed: number;
  activeMunicipalities: number;
  notificationSucceeded: number;
  notificationFailed: number;
  channelUsage: Record<string, number>;
};

export type OpsErrorGroup = {
  errorKey: string;
  category: string;
  service: string;
  pathGroup: string | null;
  statusClass: string | null;
  version: string | null;
  count: number;
  firstSeen: string;
  lastSeen: string;
  lastRequestId: string | null;
  lastJobId: string | null;
};

export type OpsJob = {
  jobId: string;
  kind: WorkerKind;
  ticketId: string;
  status: string;
  attempts: number;
  createdAt: number;
  updatedAt: number;
  lastErrorCode: string | null;
  replayable: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object';
}

async function throwApiError(response: Response, fallback: string): Promise<never> {
  if (response.status === 401) {
    clearStoredStaffSession();
  }
  let message = fallback;
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (typeof body.error?.message === 'string') {
      message = body.error.message;
    }
  } catch {
    // Keep fallback.
  }
  throw new Error(message);
}

function buildUrl(path: string, params: Record<string, string | undefined>): string {
  const url = new URL(`${config.apiBaseUrl}${path}`);
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

export async function fetchOpsOverview(range: OpsTimeRange): Promise<OpsOverview> {
  const response = await fetch(buildUrl('/v1/ops/overview', { range }), {
    headers: { ...getStaffAuthHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load operations overview.');
  }
  return (await response.json()) as OpsOverview;
}

export async function fetchOpsAlerts(range: OpsTimeRange): Promise<OpsAlert[]> {
  const response = await fetch(buildUrl('/v1/ops/alerts', { range }), {
    headers: { ...getStaffAuthHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load alerts.');
  }
  const body = (await response.json()) as { items?: OpsAlert[] };
  return Array.isArray(body.items) ? body.items : [];
}

export async function fetchOpsErrors(): Promise<OpsErrorGroup[]> {
  const response = await fetch(`${config.apiBaseUrl}/v1/ops/errors`, {
    headers: { ...getStaffAuthHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load errors.');
  }
  const body = (await response.json()) as { items?: OpsErrorGroup[] };
  return Array.isArray(body.items) ? body.items : [];
}

export async function fetchOpsWorkers(jobType?: WorkerKind): Promise<{
  queues: OpsOverview['workers'];
  jobs: OpsJob[];
}> {
  const response = await fetch(buildUrl('/v1/ops/workers', { jobType }), {
    headers: { ...getStaffAuthHeaders() },
  });
  if (!response.ok) {
    await throwApiError(response, 'Unable to load workers.');
  }
  const body = (await response.json()) as {
    queues?: OpsOverview['workers'];
    jobs?: OpsJob[];
  };
  return {
    queues: Array.isArray(body.queues) ? body.queues : [],
    jobs: Array.isArray(body.jobs) ? body.jobs : [],
  };
}

export async function acknowledgeOpsAlert(alarmName: string, note?: string): Promise<OpsAlert> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/ops/alerts/${encodeURIComponent(alarmName)}/ack`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getStaffAuthHeaders(),
      },
      body: JSON.stringify(note ? { note } : {}),
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to acknowledge the alert.');
  }
  return (await response.json()) as OpsAlert;
}

export async function replayOpsJob(jobId: string): Promise<{ jobId: string; replayed: boolean }> {
  const response = await fetch(
    `${config.apiBaseUrl}/v1/ops/workers/jobs/${encodeURIComponent(jobId)}/replay`,
    {
      method: 'POST',
      headers: { ...getStaffAuthHeaders() },
    },
  );
  if (!response.ok) {
    await throwApiError(response, 'Unable to replay the job.');
  }
  return (await response.json()) as { jobId: string; replayed: boolean };
}

export function isSafeOpsText(value: unknown): value is string {
  return typeof value === 'string' && !value.includes('<script');
}

export { isRecord };

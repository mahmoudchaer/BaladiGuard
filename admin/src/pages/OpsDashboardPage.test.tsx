import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '@/test/render';
import { OpsDashboardPage } from '@/pages/OpsDashboardPage';
import {
  acknowledgeOpsAlert,
  fetchOpsAlerts,
  fetchOpsErrors,
  fetchOpsOverview,
  fetchOpsWorkers,
  replayOpsJob,
} from '@/services/ops';

vi.mock('@/services/ops', () => ({
  fetchOpsOverview: vi.fn(),
  fetchOpsAlerts: vi.fn(),
  fetchOpsErrors: vi.fn(),
  fetchOpsWorkers: vi.fn(),
  acknowledgeOpsAlert: vi.fn(),
  replayOpsJob: vi.fn(),
}));

function installLocalStorage(role = 'developer_operator') {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => store.clear(),
    },
  });
  window.localStorage.setItem(
    'baladiguard.staffSession',
    JSON.stringify({
      username: 'operator',
      name: 'Demo Developer Operator',
      staffId: 'staff_ops_001',
      role,
      municipalityId: null,
      departmentIds: null,
      signedInAt: '2026-08-19T08:00:00Z',
      accessToken: 'test-ops-token',
    }),
  );
}

const overview = {
  generatedAt: '2026-08-19T08:00:00Z',
  telemetrySource: 'application',
  telemetryWarning: null,
  health: {
    ready: true,
    live: true,
    database: 'ok',
    configuration: 'ok',
    version: '0.1.0',
    env: 'test',
  },
  traffic: {
    requests: 12,
    errors: 0,
    errorRate: 0,
    latencyMs: 40,
    throttles: 0,
    authFailures: 0,
  },
  workers: [
    {
      kind: 'ai' as const,
      label: 'AI classification',
      deployed: true,
      pending: 1,
      running: 0,
      succeeded: 0,
      deadLettered: 0,
      oldestAgeSeconds: 12,
      retries: 0,
      lastErrorCode: null,
    },
  ],
  alerts: [],
  product: {
    reportsSubmitted: 3,
    reportsFailed: 0,
    ticketsOpen: 3,
    ticketsResolved: 0,
    ticketsClosed: 0,
    activeMunicipalities: 1,
    notificationSucceeded: 2,
    notificationFailed: 0,
    channelUsage: { EMAIL: 2 },
  },
  backup: { status: 'not_applicable', detail: 'Memory backend', source: 'application' },
  cloudwatchDashboardUrl: null,
  municipalityManagement: { available: false, issue: '322', label: 'later' },
};

describe('OpsDashboardPage', () => {
  beforeEach(() => {
    installLocalStorage();
    vi.mocked(fetchOpsOverview).mockResolvedValue(overview as never);
    vi.mocked(fetchOpsAlerts).mockResolvedValue([
      {
        alarmName: 'BaladiGuard-Sustained5xx',
        metricName: 'Http5xx',
        state: 'ALARM',
        severity: 'critical',
        reason: 'Sustained 5xx',
        runbookUrl: 'docs/production-observability.md#sustained-5xx',
        awsConsoleUrl: 'https://example.invalid/alarm',
        ackStatus: 'open',
        ackBy: null,
        ackAt: null,
        ackNote: null,
        owner: 'developer_operator',
      },
    ]);
    vi.mocked(fetchOpsErrors).mockResolvedValue([]);
    vi.mocked(fetchOpsWorkers).mockResolvedValue({ queues: overview.workers, jobs: [] });
  });

  it('renders operator overview from API telemetry', async () => {
    renderWithProviders(<OpsDashboardPage />, { route: '/ops' });
    expect(
      await screen.findByRole('heading', { level: 2, name: /operations dashboard/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Environment:\s*test/)).toBeInTheDocument();
    expect(screen.getByText(/Version:\s*0\.1\.0/)).toBeInTheDocument();
  });

  it('still renders overview when a secondary ops endpoint fails', async () => {
    vi.mocked(fetchOpsErrors).mockRejectedValue(new Error('Failed to fetch'));
    renderWithProviders(<OpsDashboardPage />, { route: '/ops' });
    expect(
      await screen.findByRole('heading', { level: 2, name: /operations dashboard/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Environment:\s*test/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/Failed to fetch/);
  });

  it('acknowledges an alert without rendering ticket text', async () => {
    vi.mocked(acknowledgeOpsAlert).mockResolvedValue({
      alarmName: 'BaladiGuard-Sustained5xx',
      metricName: 'Http5xx',
      state: 'ALARM',
      severity: 'critical',
      reason: 'Acknowledged by a developer operator.',
      runbookUrl: 'docs/production-observability.md#sustained-5xx',
      awsConsoleUrl: 'https://example.invalid/alarm',
      ackStatus: 'acknowledged',
      ackBy: 'operator',
      ackAt: '2026-08-19T08:01:00Z',
      ackNote: null,
      owner: 'developer_operator',
    });
    const user = userEvent.setup();
    renderWithProviders(<OpsDashboardPage />, { route: '/ops' });
    await user.click(await screen.findByRole('tab', { name: /alerts/i }));
    await user.click(await screen.findByRole('button', { name: /acknowledge/i }));
    await waitFor(() => {
      expect(acknowledgeOpsAlert).toHaveBeenCalledWith('BaladiGuard-Sustained5xx', undefined);
    });
    expect(screen.queryByText(/pothole/i)).not.toBeInTheDocument();
  });

  it('does not replay a job when the confirm is cancelled', async () => {
    vi.mocked(fetchOpsWorkers).mockResolvedValue({
      queues: overview.workers,
      jobs: [
        {
          jobId: 'job_replay_1',
          status: 'FAILED',
          attempts: 2,
          lastErrorCode: 'TIMEOUT',
          replayable: true,
        },
      ],
    } as never);
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderWithProviders(<OpsDashboardPage />, { route: '/ops' });
    await user.click(await screen.findByRole('tab', { name: /workers/i }));
    await user.click(await screen.findByRole('button', { name: /replay/i }));
    expect(confirm).toHaveBeenCalled();
    expect(replayOpsJob).not.toHaveBeenCalled();
    confirm.mockRestore();
  });
});

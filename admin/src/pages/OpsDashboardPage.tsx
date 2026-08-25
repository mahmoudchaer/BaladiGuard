import { useCallback, useEffect, useState } from 'react';
import { DashboardLayout } from '@/components/DashboardLayout';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  acknowledgeOpsAlert,
  fetchOpsAlerts,
  fetchOpsErrors,
  fetchOpsOverview,
  fetchOpsWorkers,
  replayOpsJob,
  type OpsAlert,
  type OpsErrorGroup,
  type OpsJob,
  type OpsOverview,
  type OpsTimeRange,
  type WorkerKind,
} from '@/services/ops';
import './OpsDashboardPage.css';

const RANGES: OpsTimeRange[] = ['1h', '6h', '24h', '7d'];
const JOB_FILTERS: Array<WorkerKind | 'all'> = [
  'all',
  'ai',
  'redaction',
  'notifications',
  'whatsapp',
  'moderation',
];

type OpsTab = 'overview' | 'alerts' | 'workers' | 'errors' | 'product';

function settledValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === 'fulfilled' ? result.value : fallback;
}

function settledError(result: PromiseSettledResult<unknown>): string | null {
  if (result.status !== 'rejected') {
    return null;
  }
  return result.reason instanceof Error ? result.reason.message : null;
}

function badgeTone(value: string): 'ok' | 'warn' | 'danger' {
  const normalized = value.toLowerCase();
  if (['ok', 'healthy', 'ready', 'true', 'cloudwatch'].includes(normalized)) {
    return 'ok';
  }
  if (['alarm', 'failed', 'degraded', 'error', 'false', 'critical'].includes(normalized)) {
    return 'danger';
  }
  return 'warn';
}

export function OpsDashboardPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<OpsTab>('overview');
  const [range, setRange] = useState<OpsTimeRange>('1h');
  const [jobType, setJobType] = useState<WorkerKind | 'all'>('all');
  const [overview, setOverview] = useState<OpsOverview | null>(null);
  const [alerts, setAlerts] = useState<OpsAlert[]>([]);
  const [errors, setErrors] = useState<OpsErrorGroup[]>([]);
  const [jobs, setJobs] = useState<OpsJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ackNote, setAckNote] = useState('');
  const [busyAlarm, setBusyAlarm] = useState<string | null>(null);
  const [busyJob, setBusyJob] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextOverview, nextAlerts, nextErrors, nextWorkers] = await Promise.allSettled([
        fetchOpsOverview(range),
        fetchOpsAlerts(range),
        fetchOpsErrors(),
        fetchOpsWorkers(jobType === 'all' ? undefined : jobType),
      ]);
      setOverview(settledValue(nextOverview, null));
      setAlerts(settledValue(nextAlerts, []));
      setErrors(settledValue(nextErrors, []));
      setJobs(settledValue(nextWorkers, { queues: [], jobs: [] }).jobs);
      setError(
        settledError(nextOverview) ??
          settledError(nextAlerts) ??
          settledError(nextErrors) ??
          settledError(nextWorkers),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('ops.loadError'));
    } finally {
      setLoading(false);
    }
  }, [jobType, range, t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleAck(alarmName: string) {
    setBusyAlarm(alarmName);
    try {
      const updated = await acknowledgeOpsAlert(alarmName, ackNote || undefined);
      setAlerts((current) =>
        current.map((item) => (item.alarmName === alarmName ? updated : item)),
      );
      setAckNote('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('ops.ackError'));
    } finally {
      setBusyAlarm(null);
    }
  }

  async function handleReplay(jobId: string) {
    if (!window.confirm(t('ops.confirmReplay'))) {
      return;
    }
    setBusyJob(jobId);
    try {
      await replayOpsJob(jobId);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('ops.replayError'));
    } finally {
      setBusyJob(null);
    }
  }

  const readyLabel = overview?.health.ready ? t('ops.yes') : t('ops.no');

  return (
    <DashboardLayout title={t('ops.title')} subtitle={t('ops.subtitle')}>
      <section className="ops-page" aria-labelledby="ops-heading">
        <header className="ops-page__header">
          <div>
            <p className="ops-page__eyebrow">{t('ops.eyebrow')}</p>
            <h2 id="ops-heading">{t('ops.title')}</h2>
            <p className="ops-page__lede">{t('ops.lede')}</p>
            {overview ? (
              <p className="ops-page__meta">
                {t('ops.updated')}: {overview.generatedAt} · {t('ops.source')}:{' '}
                {overview.telemetrySource}
              </p>
            ) : null}
          </div>
          <div className="ops-page__controls">
            <label className="ops-field">
              <span>{t('ops.timeRange')}</span>
              <select
                value={range}
                onChange={(event) => setRange(event.target.value as OpsTimeRange)}
              >
                {RANGES.map((item) => (
                  <option key={item} value={item}>
                    {t(`ops.range.${item}`)}
                  </option>
                ))}
              </select>
            </label>
            {overview?.cloudwatchDashboardUrl ? (
              <a
                className="ops-page__link"
                href={overview.cloudwatchDashboardUrl}
                target="_blank"
                rel="noreferrer"
              >
                {t('ops.openDashboard')}
              </a>
            ) : null}
            <button
              type="button"
              className="ops-page__primary"
              onClick={() => void load()}
              disabled={loading}
            >
              {t('ops.refresh')}
            </button>
          </div>
        </header>

        {overview?.telemetryWarning ? (
          <p className="ops-page__warning" role="status">
            {t('ops.telemetryFallback')}: {overview.telemetryWarning}
          </p>
        ) : null}
        {error ? (
          <p className="ops-page__error" role="alert">
            {error}
          </p>
        ) : null}

        <div className="ops-tabs" role="tablist" aria-label={t('ops.tabsLabel')}>
          {(['overview', 'alerts', 'workers', 'errors', 'product'] as OpsTab[]).map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={tab === item}
              className={tab === item ? 'ops-tabs__tab ops-tabs__tab--active' : 'ops-tabs__tab'}
              onClick={() => setTab(item)}
            >
              {t(`ops.tab.${item}`)}
            </button>
          ))}
        </div>

        {loading && !overview ? <p>{t('common.loading')}</p> : null}

        {tab === 'overview' && overview ? (
          <div className="ops-grid">
            <article
              className={`ops-metric ops-metric--${overview.health.ready ? 'ok' : 'danger'}`}
            >
              <p className="ops-metric__label">{t('ops.health')}</p>
              <p className="ops-metric__value">{readyLabel}</p>
              <p className="ops-metric__hint">
                {t('ops.env')}: {overview.health.env}
              </p>
              <p className="ops-metric__hint">
                {t('ops.version')}: {overview.health.version}
              </p>
              <p className="ops-metric__hint">
                {t('ops.database')}: {overview.health.database}
              </p>
              <p className="ops-metric__hint">
                {t('ops.source')}: {overview.telemetrySource}
              </p>
            </article>
            <article className="ops-metric">
              <p className="ops-metric__label">{t('ops.traffic')}</p>
              <p className="ops-metric__value">{overview.traffic.requests}</p>
              <p className="ops-metric__hint">
                {t('ops.errors')}: {overview.traffic.errors} · {t('ops.errorRate')}:{' '}
                {overview.traffic.errorRate}
              </p>
              <p className="ops-metric__hint">
                {t('ops.latency')}: {overview.traffic.latencyMs} ms
              </p>
            </article>
            <article className={`ops-metric ops-metric--${badgeTone(overview.backup.status)}`}>
              <p className="ops-metric__label">{t('ops.backup')}</p>
              <p className="ops-metric__value">{overview.backup.status}</p>
              <p className="ops-metric__hint">{overview.backup.detail}</p>
            </article>
            <article className="ops-metric ops-metric--warn">
              <p className="ops-metric__label">{t('ops.municipalities')}</p>
              <p className="ops-metric__value">{overview.product.activeMunicipalities}</p>
              <p className="ops-metric__hint">{t('ops.municipalitySoon')}</p>
            </article>
          </div>
        ) : null}

        {tab === 'alerts' ? (
          <div className="ops-stack">
            <label className="ops-note">
              <span>{t('ops.ackNote')}</span>
              <input
                value={ackNote}
                maxLength={200}
                placeholder={t('ops.ackNotePlaceholder')}
                onChange={(event) => setAckNote(event.target.value)}
              />
            </label>
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('ops.alarm')}</th>
                    <th>{t('ops.state')}</th>
                    <th>{t('ops.severity')}</th>
                    <th>{t('ops.reason')}</th>
                    <th>{t('ops.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.length === 0 ? (
                    <tr>
                      <td colSpan={5}>
                        <p className="ops-empty">{t('ops.emptyAlerts')}</p>
                      </td>
                    </tr>
                  ) : (
                    alerts.map((alert) => (
                      <tr key={alert.alarmName}>
                        <td>{alert.alarmName}</td>
                        <td>
                          <span className={`ops-badge ops-badge--${badgeTone(alert.state)}`}>
                            {alert.state}
                          </span>
                        </td>
                        <td>
                          <span className={`ops-badge ops-badge--${badgeTone(alert.severity)}`}>
                            {alert.severity}
                          </span>
                        </td>
                        <td>{alert.reason}</td>
                        <td>
                          <div className="ops-actions">
                            {alert.ackStatus === 'acknowledged' ? (
                              t('ops.acknowledged')
                            ) : (
                              <button
                                type="button"
                                disabled={busyAlarm === alert.alarmName}
                                onClick={() => void handleAck(alert.alarmName)}
                              >
                                {t('ops.acknowledge')}
                              </button>
                            )}
                            {alert.awsConsoleUrl ? (
                              <a
                                className="ops-page__link"
                                href={alert.awsConsoleUrl}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {t('ops.awsLink')}
                              </a>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {tab === 'workers' ? (
          <div className="ops-stack ops-workers">
            <label className="ops-field ops-workers__filter">
              <span>{t('ops.jobType')}</span>
              <select
                value={jobType}
                onChange={(event) => setJobType(event.target.value as WorkerKind | 'all')}
              >
                {JOB_FILTERS.map((item) => (
                  <option key={item} value={item}>
                    {t(`ops.jobKind.${item}`)}
                  </option>
                ))}
              </select>
            </label>
            <div className="ops-grid ops-workers__grid">
              {(overview?.workers ?? [])
                .filter((item) => jobType === 'all' || item.kind === jobType)
                .map((queue) => (
                  <article className="ops-card ops-workers__card" key={queue.kind}>
                    <h3>{queue.label}</h3>
                    <p className="ops-metric__value">{queue.pending}</p>
                    <p>
                      {t('ops.deployed')}: {queue.deployed ? t('ops.yes') : t('ops.no')}
                    </p>
                    <p>
                      {t('ops.pending')}: {queue.pending}
                    </p>
                    <p>
                      {t('ops.running')}: {queue.running}
                    </p>
                    <p>
                      {t('ops.deadLettered')}: {queue.deadLettered}
                    </p>
                  </article>
                ))}
            </div>
            <div className="ops-table-wrap ops-workers__table">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>{t('ops.jobId')}</th>
                    <th>{t('ops.status')}</th>
                    <th>{t('ops.attempts')}</th>
                    <th>{t('ops.reason')}</th>
                    <th>{t('ops.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.length === 0 ? (
                    <tr>
                      <td colSpan={5}>
                        <p className="ops-empty">{t('ops.emptyJobs')}</p>
                      </td>
                    </tr>
                  ) : (
                    jobs.map((job) => (
                      <tr key={job.jobId}>
                        <td className="ops-workers__job-id">{job.jobId}</td>
                        <td>
                          <span className={`ops-badge ops-badge--${badgeTone(job.status)}`}>
                            {job.status}
                          </span>
                        </td>
                        <td>{job.attempts}</td>
                        <td>{job.lastErrorCode ?? '—'}</td>
                        <td>
                          {job.replayable ? (
                            <button
                              type="button"
                              disabled={busyJob === job.jobId}
                              onClick={() => void handleReplay(job.jobId)}
                            >
                              {t('ops.replay')}
                            </button>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {tab === 'errors' ? (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>{t('ops.category')}</th>
                  <th>{t('ops.service')}</th>
                  <th>{t('ops.count')}</th>
                  <th>{t('ops.requestId')}</th>
                  <th>{t('ops.jobId')}</th>
                </tr>
              </thead>
              <tbody>
                {errors.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <p className="ops-empty">{t('ops.emptyErrors')}</p>
                    </td>
                  </tr>
                ) : (
                  errors.map((item) => (
                    <tr key={item.errorKey}>
                      <td>{item.category}</td>
                      <td>{item.service}</td>
                      <td>{item.count}</td>
                      <td>{item.lastRequestId ?? '—'}</td>
                      <td>{item.lastJobId ?? '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : null}

        {tab === 'product' && overview ? (
          <div className="ops-grid">
            <article className="ops-metric">
              <p className="ops-metric__label">{t('ops.reports')}</p>
              <p className="ops-metric__value">{overview.product.reportsSubmitted}</p>
              <p className="ops-metric__hint">
                {t('ops.submitted')}: {overview.product.reportsSubmitted}
              </p>
              <p className="ops-metric__hint">
                {t('ops.failed')}: {overview.product.reportsFailed}
              </p>
            </article>
            <article className="ops-metric">
              <p className="ops-metric__label">{t('ops.tickets')}</p>
              <p className="ops-metric__value">{overview.product.ticketsOpen}</p>
              <p className="ops-metric__hint">
                {t('ops.open')}: {overview.product.ticketsOpen}
              </p>
              <p className="ops-metric__hint">
                {t('ops.resolved')}: {overview.product.ticketsResolved}
              </p>
              <p className="ops-metric__hint">
                {t('ops.closed')}: {overview.product.ticketsClosed}
              </p>
            </article>
            <article className="ops-metric">
              <p className="ops-metric__label">{t('ops.notifications')}</p>
              <p className="ops-metric__value">{overview.product.notificationSucceeded}</p>
              <p className="ops-metric__hint">
                {t('ops.succeeded')}: {overview.product.notificationSucceeded}
              </p>
              <p className="ops-metric__hint">
                {t('ops.failed')}: {overview.product.notificationFailed}
              </p>
            </article>
          </div>
        ) : null}
      </section>
    </DashboardLayout>
  );
}

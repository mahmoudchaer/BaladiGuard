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
      const [nextOverview, nextAlerts, nextErrors, nextWorkers] = await Promise.all([
        fetchOpsOverview(range),
        fetchOpsAlerts(range),
        fetchOpsErrors(),
        fetchOpsWorkers(jobType === 'all' ? undefined : jobType),
      ]);
      setOverview(nextOverview);
      setAlerts(nextAlerts);
      setErrors(nextErrors);
      setJobs(nextWorkers.jobs);
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

  return (
    <DashboardLayout title={t('ops.title')} subtitle={t('ops.subtitle')}>
      <section className="ops-page" aria-labelledby="ops-heading">
        <header className="ops-page__header">
          <div>
            <p className="ops-page__eyebrow">{t('ops.eyebrow')}</p>
            <h2 id="ops-heading">{t('ops.title')}</h2>
            <p className="ops-page__lede">{t('ops.lede')}</p>
          </div>
          <div className="ops-page__controls">
            <label>
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
            <button type="button" onClick={() => void load()} disabled={loading}>
              {t('common.retry')}
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
            <article className="ops-card">
              <h3>{t('ops.health')}</h3>
              <p>
                {t('ops.env')}: {overview.health.env}
              </p>
              <p>
                {t('ops.version')}: {overview.health.version}
              </p>
              <p>
                {t('ops.ready')}: {overview.health.ready ? t('ops.yes') : t('ops.no')}
              </p>
              <p>
                {t('ops.database')}: {overview.health.database}
              </p>
              <p>
                {t('ops.source')}: {overview.telemetrySource}
              </p>
            </article>
            <article className="ops-card">
              <h3>{t('ops.traffic')}</h3>
              <p>
                {t('ops.requests')}: {overview.traffic.requests}
              </p>
              <p>
                {t('ops.errors')}: {overview.traffic.errors}
              </p>
              <p>
                {t('ops.errorRate')}: {overview.traffic.errorRate}
              </p>
              <p>
                {t('ops.latency')}: {overview.traffic.latencyMs} ms
              </p>
            </article>
            <article className="ops-card">
              <h3>{t('ops.backup')}</h3>
              <p>{overview.backup.status}</p>
              <p>{overview.backup.detail}</p>
            </article>
            <article className="ops-card">
              <h3>{t('ops.municipalities')}</h3>
              <p>{t('ops.municipalitySoon')}</p>
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
                onChange={(event) => setAckNote(event.target.value)}
              />
            </label>
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
                {alerts.map((alert) => (
                  <tr key={alert.alarmName}>
                    <td>{alert.alarmName}</td>
                    <td>{alert.state}</td>
                    <td>{alert.severity}</td>
                    <td>{alert.reason}</td>
                    <td>
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
                        <a href={alert.awsConsoleUrl} target="_blank" rel="noreferrer">
                          {t('ops.awsLink')}
                        </a>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {tab === 'workers' ? (
          <div className="ops-stack">
            <label>
              <span>{t('ops.jobType')}</span>
              <select
                value={jobType}
                onChange={(event) => setJobType(event.target.value as WorkerKind | 'all')}
              >
                {JOB_FILTERS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <div className="ops-grid">
              {(overview?.workers ?? [])
                .filter((item) => jobType === 'all' || item.kind === jobType)
                .map((queue) => (
                  <article className="ops-card" key={queue.kind}>
                    <h3>{queue.label}</h3>
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
                {jobs.map((job) => (
                  <tr key={job.jobId}>
                    <td>{job.jobId}</td>
                    <td>{job.status}</td>
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
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {tab === 'errors' ? (
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
              {errors.map((item) => (
                <tr key={item.errorKey}>
                  <td>{item.category}</td>
                  <td>{item.service}</td>
                  <td>{item.count}</td>
                  <td>{item.lastRequestId ?? '—'}</td>
                  <td>{item.lastJobId ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}

        {tab === 'product' && overview ? (
          <div className="ops-grid">
            <article className="ops-card">
              <h3>{t('ops.reports')}</h3>
              <p>
                {t('ops.submitted')}: {overview.product.reportsSubmitted}
              </p>
              <p>
                {t('ops.failed')}: {overview.product.reportsFailed}
              </p>
            </article>
            <article className="ops-card">
              <h3>{t('ops.tickets')}</h3>
              <p>
                {t('ops.open')}: {overview.product.ticketsOpen}
              </p>
              <p>
                {t('ops.resolved')}: {overview.product.ticketsResolved}
              </p>
              <p>
                {t('ops.closed')}: {overview.product.ticketsClosed}
              </p>
            </article>
            <article className="ops-card">
              <h3>{t('ops.notifications')}</h3>
              <p>
                {t('ops.succeeded')}: {overview.product.notificationSucceeded}
              </p>
              <p>
                {t('ops.failed')}: {overview.product.notificationFailed}
              </p>
            </article>
          </div>
        ) : null}
      </section>
    </DashboardLayout>
  );
}

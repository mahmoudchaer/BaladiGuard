import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DashboardLayout } from '@/components/DashboardLayout';
import { useI18n } from '@/i18n/LocaleProvider';
import { LoadingState } from '@/components/LoadingState';
import { DEPARTMENT_NAMES, departmentsForMunicipality } from '@/data/departments';
import { useStaffAuth } from '@/auth/useStaffAuth';
import {
  createTeam,
  createWorker,
  fetchWorkload,
  listTeams,
  listWorkers,
  setTeamActive,
  setWorkerActive,
  updateTeam,
  updateWorker,
} from '@/services/workforce';
import { listStaffDepartments } from '@/services/staffAccounts';
import type { WorkforceTeam, WorkforceWorker, WorkloadSnapshot } from '@/types/workforce';
import { formatStatus } from '@/utils/labels';
import type { TicketStatus } from '@/types/ticket';
import './WorkforcePage.css';

type TabId = 'directory' | 'workload';

function formatDepartments(
  ids: string[],
  names: Record<string, string> = DEPARTMENT_NAMES,
): string {
  return ids.map((id) => names[id] ?? id).join(', ');
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function WorkloadMetrics({
  counts,
  includeClosed = false,
}: {
  counts: WorkloadSnapshot['unassigned'];
  includeClosed?: boolean;
}) {
  const { t } = useI18n();
  const metrics = [
    ['queued', counts.queued],
    ['assigned', counts.assigned],
    ['inProgress', counts.inProgress],
    ['dueSoon', counts.dueSoon],
    ['overdue', counts.overdue],
    ...(includeClosed
      ? [
          ['completed', counts.completed ?? 0],
          ['cancelled', counts.cancelled ?? 0],
        ]
      : []),
  ] as Array<[string, number]>;

  return (
    <ul className="workforce-counts" aria-label={t('workforce.workload')}>
      {metrics.map(([label, count]) => (
        <li key={label}>{t(`workforce.${label}`, { count })}</li>
      ))}
    </ul>
  );
}

function DepartmentChecklist({
  selected,
  onChange,
  options,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
  options: Array<[string, string]>;
}) {
  const { t } = useI18n();
  return (
    <fieldset className="workforce-checklist">
      <legend>{t('workforce.departments')}</legend>
      {options.map(([id, name]) => (
        <label key={id}>
          <input
            type="checkbox"
            checked={selected.includes(id)}
            onChange={() => onChange(toggleValue(selected, id))}
          />
          {name}
        </label>
      ))}
    </fieldset>
  );
}

export function WorkforcePage() {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const focusWorkerId = searchParams.get('workerId');
  const focusTeamId = searchParams.get('teamId');
  const { session } = useStaffAuth();
  const isAdmin = session?.role === 'administrator';
  const municipalityId = session?.municipalityId ?? '';
  const [departmentOptions, setDepartmentOptions] = useState<Array<[string, string]>>(() =>
    departmentsForMunicipality(municipalityId),
  );
  const [departmentNames, setDepartmentNames] = useState<Record<string, string>>(DEPARTMENT_NAMES);
  const [tab, setTab] = useState<TabId>(focusWorkerId || focusTeamId ? 'directory' : 'workload');
  const [workers, setWorkers] = useState<WorkforceWorker[]>([]);
  const [teams, setTeams] = useState<WorkforceTeam[]>([]);
  const [workload, setWorkload] = useState<WorkloadSnapshot | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [workerName, setWorkerName] = useState('');
  const [workerDepartment, setWorkerDepartment] = useState(departmentOptions[0]?.[0] ?? '');
  const [teamName, setTeamName] = useState('');
  const [teamDepartment, setTeamDepartment] = useState(departmentOptions[0]?.[0] ?? '');
  const [editingWorkerId, setEditingWorkerId] = useState<string | null>(null);
  const [editWorkerName, setEditWorkerName] = useState('');
  const [editWorkerDepartments, setEditWorkerDepartments] = useState<string[]>([]);
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editTeamName, setEditTeamName] = useState('');
  const [editTeamDepartments, setEditTeamDepartments] = useState<string[]>([]);
  const [editTeamWorkerIds, setEditTeamWorkerIds] = useState<string[]>([]);
  const [editTeamLeadId, setEditTeamLeadId] = useState('');

  async function reload() {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      const [nextWorkers, nextTeams, nextWorkload] = await Promise.all([
        listWorkers(municipalityId),
        listTeams(municipalityId),
        fetchWorkload(municipalityId),
      ]);
      setWorkers(nextWorkers);
      setTeams(nextTeams);
      setWorkload(nextWorkload);
      setLoadState('ready');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.loadError'));
      setLoadState('error');
    }
  }

  useEffect(() => {
    setDepartmentOptions(departmentsForMunicipality(municipalityId));
    void listStaffDepartments()
      .then((items) => {
        if (items.length === 0) return;
        const next = items.map((item) => [item.departmentId, item.name] as [string, string]);
        setDepartmentOptions(next);
        setDepartmentNames((current) => ({
          ...current,
          ...Object.fromEntries(next),
        }));
        setWorkerDepartment((current) => current || next[0]?.[0] || '');
        setTeamDepartment((current) => current || next[0]?.[0] || '');
      })
      .catch(() => {
        // Seed catalog remains available when the live list cannot be loaded.
      });
  }, [municipalityId]);

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [municipalityId]);

  useEffect(() => {
    const targetId = focusWorkerId
      ? `worker-${focusWorkerId}`
      : focusTeamId
        ? `team-${focusTeamId}`
        : null;
    if (!targetId || loadState !== 'ready') {
      return;
    }
    document.getElementById(targetId)?.scrollIntoView({ block: 'center' });
  }, [focusTeamId, focusWorkerId, loadState]);

  const workerLookup = useMemo(
    () => Object.fromEntries(workers.map((worker) => [worker.workerId, worker.displayName])),
    [workers],
  );

  function startEditWorker(worker: WorkforceWorker) {
    setEditingWorkerId(worker.workerId);
    setEditWorkerName(worker.displayName);
    setEditWorkerDepartments([...worker.departmentIds]);
  }

  function startEditTeam(team: WorkforceTeam) {
    setEditingTeamId(team.teamId);
    setEditTeamName(team.displayName);
    setEditTeamDepartments([...team.departmentIds]);
    setEditTeamWorkerIds([...team.workerIds]);
    setEditTeamLeadId(team.leadWorkerId ?? '');
  }

  async function handleCreateWorker() {
    if (!workerName.trim()) {
      return;
    }
    try {
      setErrorMessage(null);
      await createWorker({
        municipalityId,
        displayName: workerName.trim(),
        departmentIds: [workerDepartment],
      });
      setWorkerName('');
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.createWorkerError'));
    }
  }

  async function handleCreateTeam() {
    if (!teamName.trim()) {
      return;
    }
    try {
      setErrorMessage(null);
      await createTeam({
        municipalityId,
        displayName: teamName.trim(),
        departmentIds: [teamDepartment],
      });
      setTeamName('');
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.createTeamError'));
    }
  }

  async function handleSaveWorker() {
    if (!editingWorkerId || !editWorkerName.trim() || editWorkerDepartments.length === 0) {
      return;
    }
    try {
      setErrorMessage(null);
      await updateWorker(editingWorkerId, {
        displayName: editWorkerName.trim(),
        departmentIds: editWorkerDepartments,
      });
      setEditingWorkerId(null);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.updateWorkerError'));
    }
  }

  async function handleSaveTeam() {
    if (!editingTeamId || !editTeamName.trim() || editTeamDepartments.length === 0) {
      return;
    }
    try {
      setErrorMessage(null);
      await updateTeam(editingTeamId, {
        displayName: editTeamName.trim(),
        departmentIds: editTeamDepartments,
        workerIds: editTeamWorkerIds,
        leadWorkerId: editTeamLeadId || null,
      });
      setEditingTeamId(null);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.updateTeamError'));
    }
  }

  async function handleToggleWorker(workerId: string, active: boolean) {
    if (!active && !window.confirm(t('workforce.confirmDeactivateWorker'))) {
      return;
    }
    try {
      setErrorMessage(null);
      await setWorkerActive(workerId, active);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.updateWorkerError'));
    }
  }

  async function handleToggleTeam(teamId: string, active: boolean) {
    if (!active && !window.confirm(t('workforce.confirmDeactivateTeam'))) {
      return;
    }
    try {
      setErrorMessage(null);
      await setTeamActive(teamId, active);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('workforce.updateTeamError'));
    }
  }

  return (
    <DashboardLayout title={t('workforce.title')} subtitle={t('workforce.subtitle')}>
      <div className="workforce-page">
        <div className="workforce-page__tabs" role="tablist" aria-label={t('workforce.viewsA11y')}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'workload'}
            className={`workforce-page__tab${tab === 'workload' ? ' workforce-page__tab--active' : ''}`}
            onClick={() => setTab('workload')}
          >
            {t('workforce.workload')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'directory'}
            className={`workforce-page__tab${tab === 'directory' ? ' workforce-page__tab--active' : ''}`}
            onClick={() => setTab('directory')}
          >
            {t('workforce.directory')}
          </button>
        </div>

        {errorMessage && (
          <p className="workforce-page__error" role="alert">
            {errorMessage}
          </p>
        )}
        {loadState === 'loading' && <LoadingState message={t('workforce.loading')} />}

        {loadState === 'ready' &&
        tab === 'directory' &&
        focusWorkerId &&
        !workers.some((item) => item.workerId === focusWorkerId) ? (
          <p className="workforce-page__error" role="status">
            {t('workforce.workerGone')}
          </p>
        ) : null}
        {loadState === 'ready' &&
        tab === 'directory' &&
        focusTeamId &&
        !teams.some((item) => item.teamId === focusTeamId) ? (
          <p className="workforce-page__error" role="status">
            {t('workforce.teamGone')}
          </p>
        ) : null}
        {loadState === 'ready' && tab === 'directory' && (
          <div className="workforce-page__grid">
            <section className="workforce-card">
              <h2>{t('workforce.workers')}</h2>
              {isAdmin && (
                <form
                  className="workforce-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCreateWorker();
                  }}
                >
                  <label>
                    {t('workforce.displayName')}
                    <input
                      value={workerName}
                      onChange={(event) => setWorkerName(event.target.value)}
                      placeholder={t('workforce.workerNamePlaceholder')}
                    />
                  </label>
                  <label>
                    {t('workforce.department')}
                    <select
                      value={workerDepartment}
                      onChange={(event) => setWorkerDepartment(event.target.value)}
                    >
                      {departmentOptions.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit" className="workforce-button workforce-button--primary">
                    {t('workforce.addWorker')}
                  </button>
                </form>
              )}
              <table className="workforce-table">
                <thead>
                  <tr>
                    <th>{t('workforce.name')}</th>
                    <th>{t('workforce.departments')}</th>
                    <th>{t('workforce.status')}</th>
                    {isAdmin ? <th>{t('workforce.actions')}</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {workers.map((worker) => (
                    <tr
                      key={worker.workerId}
                      id={`worker-${worker.workerId}`}
                      className={
                        focusWorkerId === worker.workerId ? 'workforce-row--focus' : undefined
                      }
                    >
                      {editingWorkerId === worker.workerId ? (
                        <td colSpan={isAdmin ? 4 : 3}>
                          <form
                            className="workforce-form"
                            onSubmit={(event) => {
                              event.preventDefault();
                              void handleSaveWorker();
                            }}
                          >
                            <label>
                              {t('workforce.displayName')}
                              <input
                                aria-label={t('workforce.editWorkerName')}
                                value={editWorkerName}
                                onChange={(event) => setEditWorkerName(event.target.value)}
                              />
                            </label>
                            <DepartmentChecklist
                              selected={editWorkerDepartments}
                              onChange={setEditWorkerDepartments}
                              options={departmentOptions}
                            />
                            <div className="workforce-form__actions">
                              <button type="submit">{t('workforce.saveWorker')}</button>
                              <button type="button" onClick={() => setEditingWorkerId(null)}>
                                {t('common.cancel')}
                              </button>
                            </div>
                          </form>
                        </td>
                      ) : (
                        <>
                          <td>{worker.displayName}</td>
                          <td>{formatDepartments(worker.departmentIds, departmentNames)}</td>
                          <td>
                            <span
                              className={`workforce-status workforce-status--${worker.active ? 'active' : 'inactive'}`}
                            >
                              {worker.active ? t('workforce.active') : t('workforce.inactive')}
                            </span>
                          </td>
                          {isAdmin ? (
                            <td>
                              <button
                                type="button"
                                className="workforce-button workforce-button--secondary"
                                onClick={() => startEditWorker(worker)}
                              >
                                {t('workforce.edit')}
                              </button>
                              <button
                                type="button"
                                className={`workforce-button ${worker.active ? 'workforce-button--danger' : 'workforce-button--primary'}`}
                                onClick={() =>
                                  void handleToggleWorker(worker.workerId, !worker.active)
                                }
                              >
                                {worker.active
                                  ? t('workforce.deactivate')
                                  : t('workforce.reactivate')}
                              </button>
                            </td>
                          ) : null}
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="workforce-card">
              <h2>{t('workforce.teams')}</h2>
              {isAdmin && (
                <form
                  className="workforce-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCreateTeam();
                  }}
                >
                  <label>
                    {t('workforce.displayName')}
                    <input
                      value={teamName}
                      onChange={(event) => setTeamName(event.target.value)}
                      placeholder={t('workforce.teamNamePlaceholder')}
                    />
                  </label>
                  <label>
                    {t('workforce.department')}
                    <select
                      value={teamDepartment}
                      onChange={(event) => setTeamDepartment(event.target.value)}
                    >
                      {departmentOptions.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit" className="workforce-button workforce-button--primary">
                    {t('workforce.addTeam')}
                  </button>
                </form>
              )}
              <table className="workforce-table">
                <thead>
                  <tr>
                    <th>{t('workforce.name')}</th>
                    <th>{t('workforce.members')}</th>
                    <th>{t('workforce.teamLead')}</th>
                    <th>{t('workforce.status')}</th>
                    {isAdmin ? <th>{t('workforce.actions')}</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {teams.map((team) => (
                    <tr
                      key={team.teamId}
                      id={`team-${team.teamId}`}
                      className={focusTeamId === team.teamId ? 'workforce-row--focus' : undefined}
                    >
                      {editingTeamId === team.teamId ? (
                        <td colSpan={isAdmin ? 5 : 4}>
                          <form
                            className="workforce-form"
                            onSubmit={(event) => {
                              event.preventDefault();
                              void handleSaveTeam();
                            }}
                          >
                            <label>
                              {t('workforce.displayName')}
                              <input
                                aria-label={t('workforce.editTeamName')}
                                value={editTeamName}
                                onChange={(event) => setEditTeamName(event.target.value)}
                              />
                            </label>
                            <DepartmentChecklist
                              selected={editTeamDepartments}
                              onChange={setEditTeamDepartments}
                              options={departmentOptions}
                            />
                            <fieldset className="workforce-checklist">
                              <legend>{t('workforce.members')}</legend>
                              {workers.map((worker) => (
                                <label key={worker.workerId}>
                                  <input
                                    type="checkbox"
                                    checked={editTeamWorkerIds.includes(worker.workerId)}
                                    onChange={() =>
                                      setEditTeamWorkerIds(
                                        toggleValue(editTeamWorkerIds, worker.workerId),
                                      )
                                    }
                                  />
                                  {worker.displayName}
                                </label>
                              ))}
                            </fieldset>
                            <label>
                              {t('workforce.teamLead')}
                              <select
                                value={editTeamLeadId}
                                onChange={(event) => setEditTeamLeadId(event.target.value)}
                                aria-label={t('workforce.teamLead')}
                              >
                                <option value="">{t('workforce.none')}</option>
                                {workers
                                  .filter((worker) => editTeamWorkerIds.includes(worker.workerId))
                                  .map((worker) => (
                                    <option key={worker.workerId} value={worker.workerId}>
                                      {worker.displayName}
                                    </option>
                                  ))}
                              </select>
                            </label>
                            <div className="workforce-form__actions">
                              <button type="submit">{t('workforce.saveTeam')}</button>
                              <button type="button" onClick={() => setEditingTeamId(null)}>
                                {t('common.cancel')}
                              </button>
                            </div>
                          </form>
                        </td>
                      ) : (
                        <>
                          <td>{team.displayName}</td>
                          <td>
                            {team.workerIds.map((id) => workerLookup[id] ?? id).join(', ') ||
                              t('workforce.none')}
                          </td>
                          <td>
                            {team.leadWorkerId
                              ? (workerLookup[team.leadWorkerId] ?? team.leadWorkerId)
                              : t('workforce.none')}
                          </td>
                          <td>
                            <span
                              className={`workforce-status workforce-status--${team.active ? 'active' : 'inactive'}`}
                            >
                              {team.active ? t('workforce.active') : t('workforce.inactive')}
                            </span>
                          </td>
                          {isAdmin ? (
                            <td>
                              <button
                                type="button"
                                className="workforce-button workforce-button--secondary"
                                onClick={() => startEditTeam(team)}
                              >
                                {t('workforce.edit')}
                              </button>
                              <button
                                type="button"
                                className={`workforce-button ${team.active ? 'workforce-button--danger' : 'workforce-button--primary'}`}
                                onClick={() => void handleToggleTeam(team.teamId, !team.active)}
                              >
                                {team.active
                                  ? t('workforce.deactivate')
                                  : t('workforce.reactivate')}
                              </button>
                            </td>
                          ) : null}
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>
        )}

        {loadState === 'ready' && tab === 'workload' && workload && (
          <div className="workforce-page__grid">
            <section className="workforce-card">
              <h2>{t('workforce.unassigned')}</h2>
              <p className="workforce-card__description">{t('workforce.unassignedDescription')}</p>
              <WorkloadMetrics counts={workload.unassigned} includeClosed />
              <ul>
                {workload.unassignedTickets.map((ticket) => (
                  <li key={ticket.ticketId}>
                    <Link to={`/tickets/${ticket.ticketId}`}>{ticket.ticketNumber}</Link>
                    {` · ${formatStatus(ticket.status as TicketStatus)}`}
                  </li>
                ))}
              </ul>
            </section>
            {[...workload.workers, ...workload.teams].map((subject) => (
              <section className="workforce-card" key={`${subject.kind}-${subject.id}`}>
                <div className="workforce-card__heading">
                  <h3>{subject.displayName}</h3>
                  <span className="workforce-card__type">
                    {subject.kind === 'team' ? t('workforce.kindTeam') : t('workforce.kindWorker')}
                    {subject.active ? '' : t('workforce.inactiveParen')}
                  </span>
                </div>
                <p className="workforce-card__description">
                  {subject.kind === 'team'
                    ? t('workforce.teamDescription')
                    : t('workforce.workerDescription')}
                </p>
                <WorkloadMetrics counts={subject.counts} />
                <table className="workforce-table">
                  <tbody>
                    {subject.tickets.map((ticket) => (
                      <tr key={ticket.ticketId}>
                        <td>
                          <Link to={`/tickets/${ticket.ticketId}`}>{ticket.ticketNumber}</Link>
                        </td>
                        <td>{formatStatus(ticket.status as TicketStatus)}</td>
                        <td>{ticket.slaState ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { DEPARTMENT_NAMES } from '@/data/departments';
import { useStaffAuth } from '@/auth/useStaffAuth';
import {
  createTeam,
  createWorker,
  fetchWorkload,
  listTeams,
  listWorkers,
  setTeamActive,
  setWorkerActive,
} from '@/services/workforce';
import type { WorkforceTeam, WorkforceWorker, WorkloadSnapshot } from '@/types/workforce';
import './WorkforcePage.css';

const BEIRUT_MUNICIPALITY_ID = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const DEPARTMENT_OPTIONS = Object.entries(DEPARTMENT_NAMES);

type TabId = 'directory' | 'workload';

function formatDepartments(ids: string[]): string {
  return ids.map((id) => DEPARTMENT_NAMES[id] ?? id).join(', ');
}

function countLine(counts: WorkloadSnapshot['unassigned']): string {
  return `${counts.queued} queued · ${counts.assigned} assigned · ${counts.inProgress} in progress · ${counts.dueSoon} due soon · ${counts.overdue} overdue`;
}

export function WorkforcePage() {
  const { session } = useStaffAuth();
  const isAdmin = session?.role === 'administrator';
  const municipalityId = session?.municipalityId ?? BEIRUT_MUNICIPALITY_ID;
  const [tab, setTab] = useState<TabId>('workload');
  const [workers, setWorkers] = useState<WorkforceWorker[]>([]);
  const [teams, setTeams] = useState<WorkforceTeam[]>([]);
  const [workload, setWorkload] = useState<WorkloadSnapshot | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [workerName, setWorkerName] = useState('');
  const [workerDepartment, setWorkerDepartment] = useState(DEPARTMENT_OPTIONS[0]?.[0] ?? '');
  const [teamName, setTeamName] = useState('');
  const [teamDepartment, setTeamDepartment] = useState(DEPARTMENT_OPTIONS[0]?.[0] ?? '');

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
      setErrorMessage(error instanceof Error ? error.message : 'Unable to load workforce.');
      setLoadState('error');
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [municipalityId]);

  const workerLookup = useMemo(
    () => Object.fromEntries(workers.map((worker) => [worker.workerId, worker.displayName])),
    [workers],
  );

  async function handleCreateWorker() {
    if (!workerName.trim()) {
      return;
    }
    await createWorker({
      municipalityId,
      displayName: workerName.trim(),
      departmentIds: [workerDepartment],
    });
    setWorkerName('');
    await reload();
  }

  async function handleCreateTeam() {
    if (!teamName.trim()) {
      return;
    }
    await createTeam({
      municipalityId,
      displayName: teamName.trim(),
      departmentIds: [teamDepartment],
    });
    setTeamName('');
    await reload();
  }

  return (
    <DashboardLayout
      title="Workforce"
      subtitle="Municipality workers, teams, and active ticket workload"
    >
      <div className="workforce-page">
        <div className="workforce-page__tabs" role="tablist" aria-label="Workforce views">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'workload'}
            className={`workforce-page__tab${tab === 'workload' ? ' workforce-page__tab--active' : ''}`}
            onClick={() => setTab('workload')}
          >
            Workload
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'directory'}
            className={`workforce-page__tab${tab === 'directory' ? ' workforce-page__tab--active' : ''}`}
            onClick={() => setTab('directory')}
          >
            Directory
          </button>
        </div>

        {errorMessage && (
          <p className="workforce-page__error" role="alert">
            {errorMessage}
          </p>
        )}
        {loadState === 'loading' && <LoadingState message="Loading workforce…" />}

        {loadState === 'ready' && tab === 'directory' && (
          <div className="workforce-page__grid">
            <section className="workforce-card">
              <h2>Workers</h2>
              {isAdmin && (
                <form
                  className="workforce-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCreateWorker();
                  }}
                >
                  <label>
                    Display name
                    <input
                      value={workerName}
                      onChange={(event) => setWorkerName(event.target.value)}
                      placeholder="Field worker name"
                    />
                  </label>
                  <label>
                    Department
                    <select
                      value={workerDepartment}
                      onChange={(event) => setWorkerDepartment(event.target.value)}
                    >
                      {DEPARTMENT_OPTIONS.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit">Add worker</button>
                </form>
              )}
              <table className="workforce-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Departments</th>
                    <th>Status</th>
                    {isAdmin ? <th>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {workers.map((worker) => (
                    <tr key={worker.workerId}>
                      <td>{worker.displayName}</td>
                      <td>{formatDepartments(worker.departmentIds)}</td>
                      <td>{worker.active ? 'Active' : 'Inactive'}</td>
                      {isAdmin ? (
                        <td>
                          <button
                            type="button"
                            onClick={() =>
                              void setWorkerActive(worker.workerId, !worker.active).then(reload)
                            }
                          >
                            {worker.active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="workforce-card">
              <h2>Teams</h2>
              {isAdmin && (
                <form
                  className="workforce-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void handleCreateTeam();
                  }}
                >
                  <label>
                    Display name
                    <input
                      value={teamName}
                      onChange={(event) => setTeamName(event.target.value)}
                      placeholder="Team name"
                    />
                  </label>
                  <label>
                    Department
                    <select
                      value={teamDepartment}
                      onChange={(event) => setTeamDepartment(event.target.value)}
                    >
                      {DEPARTMENT_OPTIONS.map(([id, name]) => (
                        <option key={id} value={id}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit">Add team</button>
                </form>
              )}
              <table className="workforce-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Members</th>
                    <th>Status</th>
                    {isAdmin ? <th>Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {teams.map((team) => (
                    <tr key={team.teamId}>
                      <td>{team.displayName}</td>
                      <td>
                        {team.workerIds.map((id) => workerLookup[id] ?? id).join(', ') || 'None'}
                      </td>
                      <td>{team.active ? 'Active' : 'Inactive'}</td>
                      {isAdmin ? (
                        <td>
                          <button
                            type="button"
                            onClick={() =>
                              void setTeamActive(team.teamId, !team.active).then(reload)
                            }
                          >
                            {team.active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        </td>
                      ) : null}
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
              <h2>Unassigned</h2>
              <p>{countLine(workload.unassigned)}</p>
              <ul>
                {workload.unassignedTickets.map((ticket) => (
                  <li key={ticket.ticketId}>
                    <Link to={`/tickets/${ticket.ticketId}`}>{ticket.ticketNumber}</Link>
                    {` · ${ticket.status}`}
                  </li>
                ))}
              </ul>
            </section>
            {[...workload.workers, ...workload.teams].map((subject) => (
              <section className="workforce-card" key={`${subject.kind}-${subject.id}`}>
                <h3>
                  {subject.displayName}{' '}
                  <small>
                    ({subject.kind}
                    {subject.active ? '' : ', inactive'})
                  </small>
                </h3>
                <ul className="workforce-counts">
                  <li>Queued {subject.counts.queued}</li>
                  <li>Assigned {subject.counts.assigned}</li>
                  <li>In progress {subject.counts.inProgress}</li>
                  <li>Due soon {subject.counts.dueSoon}</li>
                  <li>Overdue {subject.counts.overdue}</li>
                </ul>
                <table className="workforce-table">
                  <tbody>
                    {subject.tickets.map((ticket) => (
                      <tr key={ticket.ticketId}>
                        <td>
                          <Link to={`/tickets/${ticket.ticketId}`}>{ticket.ticketNumber}</Link>
                        </td>
                        <td>{ticket.status}</td>
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

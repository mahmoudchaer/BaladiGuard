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
  updateTeam,
  updateWorker,
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

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function DepartmentChecklist({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset className="workforce-checklist">
      <legend>Departments</legend>
      {DEPARTMENT_OPTIONS.map(([id, name]) => (
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
  const [editingWorkerId, setEditingWorkerId] = useState<string | null>(null);
  const [editWorkerName, setEditWorkerName] = useState('');
  const [editWorkerDepartments, setEditWorkerDepartments] = useState<string[]>([]);
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editTeamName, setEditTeamName] = useState('');
  const [editTeamDepartments, setEditTeamDepartments] = useState<string[]>([]);
  const [editTeamWorkerIds, setEditTeamWorkerIds] = useState<string[]>([]);

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
      setErrorMessage(error instanceof Error ? error.message : 'Unable to create worker.');
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
      setErrorMessage(error instanceof Error ? error.message : 'Unable to create team.');
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
      setErrorMessage(error instanceof Error ? error.message : 'Unable to update worker.');
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
      });
      setEditingTeamId(null);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to update team.');
    }
  }

  async function handleToggleWorker(workerId: string, active: boolean) {
    try {
      setErrorMessage(null);
      await setWorkerActive(workerId, active);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to update worker.');
    }
  }

  async function handleToggleTeam(teamId: string, active: boolean) {
    try {
      setErrorMessage(null);
      await setTeamActive(teamId, active);
      await reload();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to update team.');
    }
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
                              Display name
                              <input
                                aria-label="Edit worker name"
                                value={editWorkerName}
                                onChange={(event) => setEditWorkerName(event.target.value)}
                              />
                            </label>
                            <DepartmentChecklist
                              selected={editWorkerDepartments}
                              onChange={setEditWorkerDepartments}
                            />
                            <div className="workforce-form__actions">
                              <button type="submit">Save worker</button>
                              <button type="button" onClick={() => setEditingWorkerId(null)}>
                                Cancel
                              </button>
                            </div>
                          </form>
                        </td>
                      ) : (
                        <>
                          <td>{worker.displayName}</td>
                          <td>{formatDepartments(worker.departmentIds)}</td>
                          <td>{worker.active ? 'Active' : 'Inactive'}</td>
                          {isAdmin ? (
                            <td>
                              <button type="button" onClick={() => startEditWorker(worker)}>
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  void handleToggleWorker(worker.workerId, !worker.active)
                                }
                              >
                                {worker.active ? 'Deactivate' : 'Reactivate'}
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
                      {editingTeamId === team.teamId ? (
                        <td colSpan={isAdmin ? 4 : 3}>
                          <form
                            className="workforce-form"
                            onSubmit={(event) => {
                              event.preventDefault();
                              void handleSaveTeam();
                            }}
                          >
                            <label>
                              Display name
                              <input
                                aria-label="Edit team name"
                                value={editTeamName}
                                onChange={(event) => setEditTeamName(event.target.value)}
                              />
                            </label>
                            <DepartmentChecklist
                              selected={editTeamDepartments}
                              onChange={setEditTeamDepartments}
                            />
                            <fieldset className="workforce-checklist">
                              <legend>Members</legend>
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
                            <div className="workforce-form__actions">
                              <button type="submit">Save team</button>
                              <button type="button" onClick={() => setEditingTeamId(null)}>
                                Cancel
                              </button>
                            </div>
                          </form>
                        </td>
                      ) : (
                        <>
                          <td>{team.displayName}</td>
                          <td>
                            {team.workerIds.map((id) => workerLookup[id] ?? id).join(', ') ||
                              'None'}
                          </td>
                          <td>{team.active ? 'Active' : 'Inactive'}</td>
                          {isAdmin ? (
                            <td>
                              <button type="button" onClick={() => startEditTeam(team)}>
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => void handleToggleTeam(team.teamId, !team.active)}
                              >
                                {team.active ? 'Deactivate' : 'Reactivate'}
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

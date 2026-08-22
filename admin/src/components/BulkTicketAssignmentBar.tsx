import { useEffect, useMemo, useState } from 'react';
import { DEPARTMENT_OPTIONS } from '@/utils/departments';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  bulkAssignTicketDepartment,
  bulkAssignTicketWorkforce,
  type BulkMutationResponse,
} from '@/services/tickets';
import { listTeams, listWorkers } from '@/services/workforce';
import type { WorkforceTeam, WorkforceWorker } from '@/types/workforce';
import './BulkTicketAssignmentBar.css';

type BulkMode = 'department' | 'workforce';

type BulkTicketAssignmentBarProps = {
  selectedTicketIds: string[];
  ticketNumbers: Record<string, string>;
  onClear: () => void;
  onCommitted?: () => void;
};

function assignmentFingerprint(
  selectedTicketIds: string[],
  mode: BulkMode,
  departmentId: string,
  workforceValue: string,
): string {
  const ids = [...selectedTicketIds].sort().join('|');
  const target = mode === 'department' ? `dept:${departmentId}` : `wf:${workforceValue}`;
  return `${ids}|${mode}|${target}`;
}

export function BulkTicketAssignmentBar({
  selectedTicketIds,
  ticketNumbers,
  onClear,
  onCommitted,
}: BulkTicketAssignmentBarProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<BulkMode>('department');
  const [departmentId, setDepartmentId] = useState('');
  const [workforceValue, setWorkforceValue] = useState('');
  const [workers, setWorkers] = useState<WorkforceWorker[]>([]);
  const [teams, setTeams] = useState<WorkforceTeam[]>([]);
  const [busy, setBusy] = useState<'preview' | 'commit' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BulkMutationResponse | null>(null);
  const [boundPreviewFingerprint, setBoundPreviewFingerprint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([listWorkers(), listTeams()])
      .then(([nextWorkers, nextTeams]) => {
        if (!cancelled) {
          setWorkers(nextWorkers);
          setTeams(nextTeams);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setWorkers([]);
          setTeams([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedCount = selectedTicketIds.length;
  const operationFingerprint = useMemo(
    () => assignmentFingerprint(selectedTicketIds, mode, departmentId, workforceValue),
    [departmentId, mode, selectedTicketIds, workforceValue],
  );

  useEffect(() => {
    setResult(null);
    setBoundPreviewFingerprint(null);
    setError(null);
  }, [operationFingerprint]);

  const canSubmit = useMemo(() => {
    if (selectedCount === 0) return false;
    if (mode === 'department') return Boolean(departmentId);
    return Boolean(workforceValue);
  }, [departmentId, mode, selectedCount, workforceValue]);

  const previewMatchesCurrent =
    result?.dryRun === true && boundPreviewFingerprint === operationFingerprint;
  const canCommit = canSubmit && previewMatchesCurrent;

  async function run(dryRun: boolean) {
    if (!canSubmit) {
      setError(t('tickets.bulk.needTarget'));
      return;
    }
    if (!dryRun && !previewMatchesCurrent) {
      setError(t('tickets.bulk.needPreview'));
      return;
    }
    setBusy(dryRun ? 'preview' : 'commit');
    setError(null);
    try {
      const next =
        mode === 'department'
          ? await bulkAssignTicketDepartment({
              ticketIds: selectedTicketIds,
              departmentId,
              dryRun,
            })
          : await bulkAssignTicketWorkforce({
              ticketIds: selectedTicketIds,
              workerId: workforceValue.startsWith('worker:')
                ? workforceValue.slice('worker:'.length)
                : null,
              teamId: workforceValue.startsWith('team:')
                ? workforceValue.slice('team:'.length)
                : null,
              dryRun,
            });
      setResult(next);
      if (dryRun) {
        setBoundPreviewFingerprint(operationFingerprint);
      } else {
        setBoundPreviewFingerprint(null);
        onCommitted?.();
      }
    } catch (err) {
      setResult(null);
      setBoundPreviewFingerprint(null);
      setError(err instanceof Error ? err.message : t('errors.generic'));
    } finally {
      setBusy(null);
    }
  }

  if (selectedCount === 0) {
    return null;
  }

  return (
    <section className="bulk-assign" aria-label={t('tickets.bulk.title')}>
      <div className="bulk-assign__row">
        <p className="bulk-assign__count">{t('tickets.bulk.selected', { count: selectedCount })}</p>
        <label>
          {t('tickets.bulk.mode')}
          <select
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as BulkMode);
            }}
          >
            <option value="department">{t('tickets.bulk.modeDepartment')}</option>
            <option value="workforce">{t('tickets.bulk.modeWorkforce')}</option>
          </select>
        </label>
        {mode === 'department' ? (
          <label>
            {t('tickets.bulk.department')}
            <select
              value={departmentId}
              onChange={(event) => {
                setDepartmentId(event.target.value);
              }}
            >
              <option value="">{t('tickets.bulk.chooseDepartment')}</option>
              {DEPARTMENT_OPTIONS.map((department) => (
                <option key={department.departmentId} value={department.departmentId}>
                  {department.name}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label>
            {t('tickets.bulk.workforce')}
            <select
              value={workforceValue}
              onChange={(event) => {
                setWorkforceValue(event.target.value);
              }}
            >
              <option value="">{t('tickets.bulk.chooseWorkforce')}</option>
              {workers
                .filter((worker) => worker.active)
                .map((worker) => (
                  <option key={worker.workerId} value={`worker:${worker.workerId}`}>
                    {worker.displayName}
                  </option>
                ))}
              {teams
                .filter((team) => team.active)
                .map((team) => (
                  <option key={team.teamId} value={`team:${team.teamId}`}>
                    {team.displayName}
                  </option>
                ))}
            </select>
          </label>
        )}
        <div className="bulk-assign__actions">
          <button type="button" onClick={() => void run(true)} disabled={Boolean(busy)}>
            {busy === 'preview' ? t('tickets.bulk.previewing') : t('tickets.bulk.preview')}
          </button>
          <button
            type="button"
            onClick={() => void run(false)}
            disabled={Boolean(busy) || !canCommit}
            title={canCommit ? undefined : t('tickets.bulk.needPreview')}
          >
            {busy === 'commit' ? t('tickets.bulk.committing') : t('tickets.bulk.commit')}
          </button>
          <button type="button" onClick={onClear} disabled={Boolean(busy)}>
            {t('tickets.bulk.clear')}
          </button>
        </div>
      </div>
      {error ? (
        <p className="bulk-assign__error" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <div className="bulk-assign__results" role="status">
          <p>
            {result.dryRun ? t('tickets.bulk.previewTitle') : t('tickets.bulk.commitTitle')}{' '}
            {t('tickets.bulk.succeeded', { count: result.succeeded })} ·{' '}
            {t('tickets.bulk.failed', { count: result.failed })}
          </p>
          <ul>
            {result.items.map((item) => (
              <li key={item.ticketId}>
                {ticketNumbers[item.ticketId] ?? item.ticketId}:{' '}
                {item.ok
                  ? t('tickets.bulk.itemOk')
                  : `${t('tickets.bulk.itemFailed')}${item.message ? ` — ${item.message}` : ''}`}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

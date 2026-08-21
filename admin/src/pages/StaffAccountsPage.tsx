import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '@/components/DashboardLayout';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { LoadingState } from '@/components/LoadingState';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  DEPARTMENT_NAMES,
  MUNICIPALITY_NAMES,
  departmentsForMunicipality,
} from '@/data/departments';
import {
  createStaffAccount,
  listStaffAccounts,
  listStaffDepartments,
  setStaffAccountActive,
  updateStaffAccount,
} from '@/services/staffAccounts';
import type { StaffAccount, StaffAccountRole } from '@/types/staffAccount';
import './StaffAccountsPage.css';

type CreateForm = {
  username: string;
  name: string;
  email: string;
  password: string;
  role: StaffAccountRole;
  municipalityId: string;
  departmentIds: string[];
};

type EditForm = {
  role: StaffAccountRole;
  municipalityId: string;
  departmentIds: string[];
};

const EMPTY_CREATE: CreateForm = {
  username: '',
  name: '',
  email: '',
  password: '',
  role: 'municipal_staff',
  municipalityId: '',
  departmentIds: [],
};

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function departmentLabel(
  ids: string[],
  unknownLabel: string,
  names: Record<string, string> = DEPARTMENT_NAMES,
): string {
  return ids.map((id) => names[id] ?? `${unknownLabel} ${id}`).join(', ');
}

function roleLabel(role: StaffAccountRole, t: (key: string) => string): string {
  return t(
    role === 'administrator' ? 'staffAccounts.administrator' : 'staffAccounts.municipalStaff',
  );
}

function validateScope(
  role: StaffAccountRole,
  municipalityId: string,
  departmentIds: string[],
  t: (key: string) => string,
): string | null {
  if (role !== 'municipal_staff') {
    return t('staffAccounts.municipalStaffOnly');
  }
  if (!municipalityId.trim()) {
    return t('staffAccounts.municipalityRequired');
  }
  if (departmentIds.length === 0) {
    return t('staffAccounts.departmentRequired');
  }
  return null;
}

function ScopeFields({
  municipalityId,
  departmentIds,
  departmentOptions,
  hintId,
  onDepartmentsChange,
}: {
  municipalityId: string;
  departmentIds: string[];
  departmentOptions: Array<[string, string]>;
  hintId: string;
  onDepartmentsChange: (value: string[]) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="staff-accounts__scope">
      <label className="staff-accounts__field">
        <span>{t('staffAccounts.municipality')}</span>
        <select value={municipalityId} disabled aria-describedby={hintId} required>
          <option value="">{t('staffAccounts.selectMunicipality')}</option>
          <option value={municipalityId}>
            {MUNICIPALITY_NAMES[municipalityId] ?? municipalityId}
          </option>
        </select>
      </label>
      <fieldset className="staff-accounts__departments">
        <legend>{t('staffAccounts.departments')}</legend>
        <div className="staff-accounts__department-grid">
          {departmentOptions.map(([id, name]) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={departmentIds.includes(id)}
                onChange={() => onDepartmentsChange(toggleValue(departmentIds, id))}
              />
              {name}
            </label>
          ))}
        </div>
      </fieldset>
      <p id={hintId} className="staff-accounts__hint">
        {t('staffAccounts.municipalScope')}
      </p>
    </div>
  );
}

export function StaffAccountsPage() {
  const { t } = useI18n();
  const { session } = useStaffAuth();
  const [accounts, setAccounts] = useState<StaffAccount[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [query, setQuery] = useState('');
  const [createForm, setCreateForm] = useState<CreateForm>(EMPTY_CREATE);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [savingCreate, setSavingCreate] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [departmentOptions, setDepartmentOptions] = useState<Array<[string, string]>>([]);
  const [departmentNames, setDepartmentNames] = useState<Record<string, string>>(DEPARTMENT_NAMES);
  const createInFlight = useRef(false);
  const mutationInFlight = useRef<Set<string>>(new Set());

  async function loadAccounts() {
    setLoadState('loading');
    setErrorMessage(null);
    try {
      setAccounts(await listStaffAccounts());
      setLoadState('ready');
    } catch (error) {
      setLoadState('error');
      setErrorMessage(error instanceof Error ? error.message : t('staffAccounts.loadError'));
    }
  }

  useEffect(() => {
    void loadAccounts();
    // The translation function is stable for the active locale; this is a route-entry load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const scopedMunicipalityId = session?.municipalityId ?? '';

  useEffect(() => {
    setDepartmentOptions(departmentsForMunicipality(scopedMunicipalityId));
    void listStaffDepartments()
      .then((items) => {
        if (items.length === 0) return;
        setDepartmentOptions(items.map((item) => [item.departmentId, item.name]));
        setDepartmentNames((current) => ({
          ...current,
          ...Object.fromEntries(items.map((item) => [item.departmentId, item.name])),
        }));
      })
      .catch(() => {
        // Seed catalog remains available when the live list cannot be loaded.
      });
  }, [scopedMunicipalityId]);

  useEffect(() => {
    if (!scopedMunicipalityId) return;
    setCreateForm((current) =>
      current.municipalityId ? current : { ...current, municipalityId: scopedMunicipalityId },
    );
  }, [scopedMunicipalityId]);

  const visibleAccounts = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return accounts;
    }
    return accounts.filter((account) =>
      [
        account.name,
        account.username,
        account.email,
        account.role,
        account.municipalityId ?? '',
        ...(account.departmentIds ?? []),
      ].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [accounts, query]);

  function updateCreate<K extends keyof CreateForm>(key: K, value: CreateForm[K]) {
    setCreateForm((current) => ({ ...current, [key]: value }));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (createInFlight.current) return;
    setErrorMessage(null);
    setSuccessMessage(null);
    const scopeError = validateScope(
      createForm.role,
      scopedMunicipalityId,
      createForm.departmentIds,
      t,
    );
    if (scopeError) {
      setErrorMessage(scopeError);
      return;
    }
    createInFlight.current = true;
    setSavingCreate(true);
    try {
      const created = await createStaffAccount({
        username: createForm.username.trim(),
        name: createForm.name.trim(),
        email: createForm.email.trim(),
        password: createForm.password,
        role: createForm.role,
        municipalityId: scopedMunicipalityId,
        departmentIds: createForm.departmentIds,
      });
      setAccounts((current) => [created, ...current]);
      setCreateForm({ ...EMPTY_CREATE, municipalityId: scopedMunicipalityId });
      setSuccessMessage(t('staffAccounts.created'));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('staffAccounts.createError'));
    } finally {
      createInFlight.current = false;
      setSavingCreate(false);
    }
  }

  function beginEdit(account: StaffAccount) {
    setEditingId(account.staffId);
    setEditForm({
      role: account.role,
      municipalityId: account.municipalityId ?? '',
      departmentIds: account.departmentIds ?? [],
    });
    setErrorMessage(null);
    setSuccessMessage(null);
  }

  async function saveEdit(account: StaffAccount) {
    if (!editForm || mutationInFlight.current.has(account.staffId)) return;
    const scopeError = validateScope(
      editForm.role,
      scopedMunicipalityId,
      editForm.departmentIds,
      t,
    );
    if (scopeError) {
      setErrorMessage(scopeError);
      return;
    }
    const roleChanged = editForm.role !== account.role;
    if (
      roleChanged &&
      !window.confirm(
        t('staffAccounts.roleChangeConfirm', {
          name: account.name,
          role: roleLabel(editForm.role, t),
        }),
      )
    )
      return;
    mutationInFlight.current.add(account.staffId);
    setBusyId(account.staffId);
    setErrorMessage(null);
    try {
      const updated = await updateStaffAccount(account.staffId, {
        ...(roleChanged ? { role: editForm.role } : {}),
        municipalityId: scopedMunicipalityId,
        departmentIds: editForm.departmentIds,
      });
      setAccounts((current) =>
        current.map((item) => (item.staffId === updated.staffId ? updated : item)),
      );
      setEditingId(null);
      setEditForm(null);
      setSuccessMessage(t('staffAccounts.updated'));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('staffAccounts.updateError'));
    } finally {
      mutationInFlight.current.delete(account.staffId);
      setBusyId(null);
    }
  }

  async function toggleActive(account: StaffAccount) {
    if (mutationInFlight.current.has(account.staffId)) return;
    if (account.active && account.staffId === session?.staffId) {
      setErrorMessage(t('staffAccounts.cannotDeactivateSelf'));
      return;
    }
    const activeAdministrators = accounts.filter(
      (item) => item.role === 'administrator' && item.active,
    ).length;
    if (account.active && account.role === 'administrator' && activeAdministrators <= 1) {
      setErrorMessage(t('staffAccounts.cannotDeactivateLastAdministrator'));
      return;
    }
    const actionKey = account.active
      ? 'staffAccounts.deactivateConfirm'
      : 'staffAccounts.reactivateConfirm';
    if (!window.confirm(t(actionKey, { name: account.name }))) return;
    mutationInFlight.current.add(account.staffId);
    setBusyId(account.staffId);
    setErrorMessage(null);
    try {
      const updated = await setStaffAccountActive(account.staffId, !account.active);
      setAccounts((current) =>
        current.map((item) => (item.staffId === updated.staffId ? updated : item)),
      );
      setSuccessMessage(
        t(account.active ? 'staffAccounts.deactivated' : 'staffAccounts.reactivated'),
      );
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('staffAccounts.statusError'));
    } finally {
      mutationInFlight.current.delete(account.staffId);
      setBusyId(null);
    }
  }

  return (
    <DashboardLayout title={t('staffAccounts.title')} subtitle={t('staffAccounts.subtitle')}>
      <div className="staff-accounts">
        <header className="staff-accounts__hero">
          <div>
            <p className="staff-accounts__eyebrow">{t('staffAccounts.eyebrow')}</p>
            <h2>{t('staffAccounts.title')}</h2>
            <p>{t('staffAccounts.description')}</p>
          </div>
          <Link className="staff-accounts__secondary-link" to="/workforce">
            {t('staffAccounts.openWorkforce')}
          </Link>
        </header>

        {errorMessage && (
          <div className="staff-accounts__feedback staff-accounts__feedback--error" role="alert">
            {errorMessage}
          </div>
        )}
        {successMessage && (
          <div className="staff-accounts__feedback staff-accounts__feedback--success" role="status">
            {successMessage}
          </div>
        )}

        <section
          className="staff-accounts__card staff-accounts__create-card"
          aria-labelledby="staff-create-heading"
        >
          <div className="staff-accounts__card-heading">
            <div>
              <p className="staff-accounts__eyebrow">{t('staffAccounts.createEyebrow')}</p>
              <h3 id="staff-create-heading">{t('staffAccounts.createTitle')}</h3>
            </div>
            <span className="staff-accounts__security-note">{t('staffAccounts.passwordNote')}</span>
          </div>
          <form className="staff-accounts__form" onSubmit={handleCreate}>
            <label className="staff-accounts__field">
              <span>{t('staffAccounts.name')}</span>
              <input
                required
                value={createForm.name}
                onChange={(e) => updateCreate('name', e.target.value)}
              />
            </label>
            <label className="staff-accounts__field">
              <span>{t('staffAccounts.username')}</span>
              <input
                required
                autoComplete="off"
                value={createForm.username}
                onChange={(e) => updateCreate('username', e.target.value)}
              />
            </label>
            <label className="staff-accounts__field">
              <span>{t('staffAccounts.email')}</span>
              <input
                required
                type="email"
                value={createForm.email}
                onChange={(e) => updateCreate('email', e.target.value)}
              />
            </label>
            <label className="staff-accounts__field">
              <span>{t('staffAccounts.initialPassword')}</span>
              <input
                required
                minLength={8}
                type="password"
                autoComplete="new-password"
                value={createForm.password}
                onChange={(e) => updateCreate('password', e.target.value)}
              />
            </label>
            <label className="staff-accounts__field">
              <span>{t('staffAccounts.role')}</span>
              <select
                value={createForm.role}
                onChange={(e) => updateCreate('role', e.target.value as StaffAccountRole)}
              >
                <option value="municipal_staff">{roleLabel('municipal_staff', t)}</option>
              </select>
            </label>
            <ScopeFields
              hintId="create-staff-scope-hint"
              municipalityId={scopedMunicipalityId || createForm.municipalityId}
              departmentIds={createForm.departmentIds}
              departmentOptions={departmentOptions}
              onDepartmentsChange={(value) => updateCreate('departmentIds', value)}
            />
            <div className="staff-accounts__form-actions">
              <button
                className="staff-accounts__primary-button"
                type="submit"
                disabled={savingCreate}
              >
                {savingCreate ? t('staffAccounts.creating') : t('staffAccounts.create')}
              </button>
            </div>
          </form>
        </section>

        <section className="staff-accounts__card" aria-labelledby="staff-directory-heading">
          <div className="staff-accounts__directory-heading">
            <div>
              <p className="staff-accounts__eyebrow">{t('staffAccounts.directoryEyebrow')}</p>
              <h3 id="staff-directory-heading">{t('staffAccounts.directoryTitle')}</h3>
            </div>
            <label className="staff-accounts__search">
              <span className="sr-only">{t('staffAccounts.searchLabel')}</span>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('staffAccounts.searchPlaceholder')}
              />
            </label>
          </div>
          {loadState === 'loading' && <LoadingState message={t('staffAccounts.loading')} />}
          {loadState === 'error' && (
            <div className="staff-accounts__retry">
              <p>{t('staffAccounts.loadError')}</p>
              <button type="button" onClick={() => void loadAccounts()}>
                {t('common.retry')}
              </button>
            </div>
          )}
          {loadState === 'ready' && visibleAccounts.length === 0 && (
            <p className="staff-accounts__empty">
              {query ? t('staffAccounts.noMatches') : t('staffAccounts.empty')}
            </p>
          )}
          {loadState === 'ready' && visibleAccounts.length > 0 && (
            <div className="staff-accounts__table-wrap">
              <table className="staff-accounts__table">
                <thead>
                  <tr>
                    <th>{t('staffAccounts.name')}</th>
                    <th>{t('staffAccounts.role')}</th>
                    <th>{t('staffAccounts.scope')}</th>
                    <th>{t('staffAccounts.status')}</th>
                    <th>
                      <span className="sr-only">{t('staffAccounts.actions')}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleAccounts.map((account) => {
                    const editing = editingId === account.staffId && editForm;
                    return (
                      <tr
                        key={account.staffId}
                        className={
                          editing
                            ? 'staff-accounts__row staff-accounts__row--editing'
                            : 'staff-accounts__row'
                        }
                      >
                        <td>
                          <strong>{account.name}</strong>
                          <span className="staff-accounts__meta">
                            {account.username} · {account.email}
                          </span>
                        </td>
                        <td>
                          {editing ? (
                            <select
                              aria-label={t('staffAccounts.editRole')}
                              value={editForm.role}
                              onChange={(e) =>
                                setEditForm({
                                  ...editForm,
                                  role: e.target.value as StaffAccountRole,
                                })
                              }
                            >
                              <option value="municipal_staff">
                                {roleLabel('municipal_staff', t)}
                              </option>
                            </select>
                          ) : (
                            roleLabel(account.role, t)
                          )}
                        </td>
                        <td>
                          {editing ? (
                            <ScopeFields
                              hintId={`edit-${account.staffId}-scope-hint`}
                              municipalityId={scopedMunicipalityId || editForm.municipalityId}
                              departmentIds={editForm.departmentIds}
                              departmentOptions={departmentOptions}
                              onDepartmentsChange={(value) =>
                                setEditForm({ ...editForm, departmentIds: value })
                              }
                            />
                          ) : (
                            <>
                              <span>
                                {MUNICIPALITY_NAMES[account.municipalityId ?? ''] ??
                                  account.municipalityId}
                              </span>
                              <span className="staff-accounts__meta">
                                {departmentLabel(
                                  account.departmentIds ?? [],
                                  t('staffAccounts.unknownDepartment'),
                                  departmentNames,
                                )}
                              </span>
                            </>
                          )}
                        </td>
                        <td>
                          <span
                            className={`staff-accounts__status staff-accounts__status--${account.active ? 'active' : 'inactive'}`}
                          >
                            {account.active
                              ? t('staffAccounts.active')
                              : t('staffAccounts.inactive')}
                          </span>
                        </td>
                        <td>
                          <div className="staff-accounts__row-actions">
                            {editing ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => void saveEdit(account)}
                                  disabled={
                                    busyId === account.staffId ||
                                    (account.active && account.staffId === session?.staffId) ||
                                    (account.active &&
                                      account.role === 'administrator' &&
                                      accounts.filter(
                                        (item) => item.role === 'administrator' && item.active,
                                      ).length <= 1)
                                  }
                                >
                                  {busyId === account.staffId
                                    ? t('staffAccounts.saving')
                                    : t('common.save')}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingId(null);
                                    setEditForm(null);
                                  }}
                                >
                                  {t('common.cancel')}
                                </button>
                              </>
                            ) : (
                              <>
                                <button type="button" onClick={() => beginEdit(account)}>
                                  {t('staffAccounts.edit')}
                                </button>
                                <button
                                  type="button"
                                  className="staff-accounts__danger-button"
                                  onClick={() => void toggleActive(account)}
                                  disabled={busyId === account.staffId}
                                >
                                  {account.active
                                    ? t('staffAccounts.deactivate')
                                    : t('staffAccounts.reactivate')}
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

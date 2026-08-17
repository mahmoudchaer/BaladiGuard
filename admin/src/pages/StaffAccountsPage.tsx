import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { useI18n } from '@/i18n/LocaleProvider';
import { DEPARTMENT_NAMES } from '@/data/departments';
import {
  createStaffAccount,
  listStaffAccounts,
  setStaffAccountActive,
  updateStaffAccount,
} from '@/services/staffAccounts';
import type { StaffAccount, StaffAccountRole } from '@/types/staffAccount';
import './StaffAccountsPage.css';

const DEPARTMENT_OPTIONS = Object.entries(DEPARTMENT_NAMES);

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

function departmentLabel(ids: string[], unknownLabel: string): string {
  return ids.map((id) => DEPARTMENT_NAMES[id] ?? `${unknownLabel} ${id}`).join(', ');
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
  if (role === 'administrator') {
    return null;
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
  role,
  municipalityId,
  departmentIds,
  hintId,
  onMunicipalityChange,
  onDepartmentsChange,
}: {
  role: StaffAccountRole;
  municipalityId: string;
  departmentIds: string[];
  hintId: string;
  onMunicipalityChange: (value: string) => void;
  onDepartmentsChange: (value: string[]) => void;
}) {
  const { t } = useI18n();
  const isAdministrator = role === 'administrator';
  return (
    <div className="staff-accounts__scope">
      <label className="staff-accounts__field">
        <span>{t('staffAccounts.municipality')}</span>
        <input
          value={isAdministrator ? '' : municipalityId}
          onChange={(event) => onMunicipalityChange(event.target.value)}
          placeholder={t('staffAccounts.municipalityPlaceholder')}
          disabled={isAdministrator}
          aria-describedby={hintId}
        />
      </label>
      <fieldset className="staff-accounts__departments">
        <legend>{t('staffAccounts.departments')}</legend>
        <div className="staff-accounts__department-grid">
          {DEPARTMENT_OPTIONS.map(([id, name]) => (
            <label key={id}>
              <input
                type="checkbox"
                checked={!isAdministrator && departmentIds.includes(id)}
                disabled={isAdministrator}
                onChange={() => onDepartmentsChange(toggleValue(departmentIds, id))}
              />
              {name}
            </label>
          ))}
        </div>
      </fieldset>
      <p id={hintId} className="staff-accounts__hint">
        {isAdministrator ? t('staffAccounts.globalScope') : t('staffAccounts.municipalScope')}
      </p>
    </div>
  );
}

export function StaffAccountsPage() {
  const { t } = useI18n();
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
    setErrorMessage(null);
    setSuccessMessage(null);
    const scopeError = validateScope(
      createForm.role,
      createForm.municipalityId,
      createForm.departmentIds,
      t,
    );
    if (scopeError) {
      setErrorMessage(scopeError);
      return;
    }
    setSavingCreate(true);
    try {
      const created = await createStaffAccount({
        username: createForm.username.trim(),
        name: createForm.name.trim(),
        email: createForm.email.trim(),
        password: createForm.password,
        role: createForm.role,
        municipalityId:
          createForm.role === 'administrator' ? null : createForm.municipalityId.trim(),
        departmentIds: createForm.role === 'administrator' ? null : createForm.departmentIds,
      });
      setAccounts((current) => [created, ...current]);
      setCreateForm(EMPTY_CREATE);
      setSuccessMessage(t('staffAccounts.created'));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t('staffAccounts.createError'));
    } finally {
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
    if (!editForm) return;
    const scopeError = validateScope(
      editForm.role,
      editForm.municipalityId,
      editForm.departmentIds,
      t,
    );
    if (scopeError) {
      setErrorMessage(scopeError);
      return;
    }
    setBusyId(account.staffId);
    setErrorMessage(null);
    try {
      const updated = await updateStaffAccount(account.staffId, {
        role: editForm.role,
        municipalityId: editForm.role === 'administrator' ? null : editForm.municipalityId.trim(),
        departmentIds: editForm.role === 'administrator' ? null : editForm.departmentIds,
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
      setBusyId(null);
    }
  }

  async function toggleActive(account: StaffAccount) {
    const actionKey = account.active ? 'deactivateConfirm' : 'reactivateConfirm';
    if (!window.confirm(t(actionKey, { name: account.name }))) return;
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
                <option value="administrator">{roleLabel('administrator', t)}</option>
              </select>
            </label>
            <ScopeFields
              hintId="create-staff-scope-hint"
              role={createForm.role}
              municipalityId={createForm.municipalityId}
              departmentIds={createForm.departmentIds}
              onMunicipalityChange={(value) => updateCreate('municipalityId', value)}
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
                              <option value="administrator">{roleLabel('administrator', t)}</option>
                            </select>
                          ) : (
                            roleLabel(account.role, t)
                          )}
                        </td>
                        <td>
                          {editing ? (
                            <ScopeFields
                              hintId={`edit-${account.staffId}-scope-hint`}
                              role={editForm.role}
                              municipalityId={editForm.municipalityId}
                              departmentIds={editForm.departmentIds}
                              onMunicipalityChange={(value) =>
                                setEditForm({ ...editForm, municipalityId: value })
                              }
                              onDepartmentsChange={(value) =>
                                setEditForm({ ...editForm, departmentIds: value })
                              }
                            />
                          ) : account.role === 'administrator' ? (
                            t('staffAccounts.global')
                          ) : (
                            <>
                              <span>{account.municipalityId}</span>
                              <span className="staff-accounts__meta">
                                {departmentLabel(
                                  account.departmentIds ?? [],
                                  t('staffAccounts.unknownDepartment'),
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
                                  disabled={busyId === account.staffId}
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

import { type FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { DashboardLayout } from '@/components/DashboardLayout';
import { LoadingState } from '@/components/LoadingState';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  createMunicipality,
  listMunicipalities,
  overrideTicketMunicipality,
  previewMunicipalityRouting,
  provisionMunicipalityAdmin,
  updateMunicipality,
  type MunicipalityProfile,
  type ServiceDomain,
} from '@/services/municipalities';
import './OpsDashboardPage.css';
import './MunicipalitiesPage.css';

const SERVICE_DOMAINS: ServiceDomain[] = [
  'roads',
  'waste',
  'lighting',
  'water',
  'noise',
  'traffic',
  'drainage',
  'facilities',
  'electricity',
];

type ProfileForm = {
  name: string;
  description: string;
  city: string;
  serviceDomains: ServiceDomain[];
  minLatitude: string;
  maxLatitude: string;
  minLongitude: string;
  maxLongitude: string;
  active: boolean;
};

const EMPTY_FORM: ProfileForm = {
  name: '',
  description: '',
  city: '',
  serviceDomains: ['roads'],
  minLatitude: '33.84',
  maxLatitude: '33.93',
  minLongitude: '35.45',
  maxLongitude: '35.58',
  active: true,
};

function toggleDomain(values: ServiceDomain[], value: ServiceDomain): ServiceDomain[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function toInput(profile: MunicipalityProfile): ProfileForm {
  return {
    name: profile.name,
    description: profile.description,
    city: profile.city ?? '',
    serviceDomains: profile.serviceDomains,
    minLatitude: String(profile.bounds.minLatitude),
    maxLatitude: String(profile.bounds.maxLatitude),
    minLongitude: String(profile.bounds.minLongitude),
    maxLongitude: String(profile.bounds.maxLongitude),
    active: profile.active,
  };
}

function toPayload(form: ProfileForm) {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    city: form.city.trim() || undefined,
    serviceDomains: form.serviceDomains,
    bounds: {
      minLatitude: Number(form.minLatitude),
      maxLatitude: Number(form.maxLatitude),
      minLongitude: Number(form.minLongitude),
      maxLongitude: Number(form.maxLongitude),
    },
    active: form.active,
  };
}

export function MunicipalitiesPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<MunicipalityProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const editFormRef = useRef<HTMLFormElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [adminForm, setAdminForm] = useState({
    municipalityId: '',
    username: '',
    name: '',
    email: '',
    password: '',
  });
  const [preview, setPreview] = useState({
    latitude: '33.896112',
    longitude: '35.478419',
    category: 'road_damage',
    result: '',
  });
  const [overrideForm, setOverrideForm] = useState({
    ticketId: '',
    municipalityId: '',
    reasonCode: 'DEVELOPER_REASSIGN',
  });

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setItems(await listMunicipalities());
    } catch (err) {
      setError(err instanceof Error ? err.message : t('municipalities.loadError'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedOverrideOptions = useMemo(() => items.filter((item) => item.active), [items]);

  function handleEdit(item: MunicipalityProfile) {
    setEditingId(item.municipalityId);
    setForm(toInput(item));
    window.requestAnimationFrame(() => {
      editFormRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
      nameInputRef.current?.focus();
    });
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    const payload = toPayload(form);
    if (editingId && !payload.active && !window.confirm(t('municipalities.confirmDeactivate'))) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await updateMunicipality(editingId, payload);
      } else {
        await createMunicipality(payload);
      }
      setForm(EMPTY_FORM);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('municipalities.saveError'));
    } finally {
      setSaving(false);
    }
  }

  async function handleProvision(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm(t('municipalities.confirmProvision'))) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await provisionMunicipalityAdmin(adminForm.municipalityId, {
        username: adminForm.username,
        name: adminForm.name,
        email: adminForm.email,
        password: adminForm.password,
      });
      setAdminForm({ municipalityId: '', username: '', name: '', email: '', password: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('municipalities.adminError'));
    } finally {
      setSaving(false);
    }
  }

  async function handlePreview(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = await previewMunicipalityRouting({
        latitude: Number(preview.latitude),
        longitude: Number(preview.longitude),
        category: preview.category,
      });
      const owner = result.decision.municipalityId ?? t('municipalities.unassigned');
      setPreview((current) => ({
        ...current,
        result: `${result.decision.status} · ${owner} · ${result.decision.reason}`,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('municipalities.previewError'));
    }
  }

  async function handleOverride(event: FormEvent) {
    event.preventDefault();
    if (!window.confirm(t('municipalities.confirmOverride'))) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await overrideTicketMunicipality(overrideForm.ticketId.trim(), {
        municipalityId: overrideForm.municipalityId || null,
        reasonCode: overrideForm.reasonCode,
      });
      setOverrideForm({ ticketId: '', municipalityId: '', reasonCode: 'DEVELOPER_REASSIGN' });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('municipalities.overrideError'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <DashboardLayout title={t('municipalities.title')} subtitle={t('municipalities.subtitle')}>
      <div className="ops-page municipalities-page">
        <header className="ops-page__header">
          <div>
            <p className="ops-page__eyebrow">{t('municipalities.eyebrow')}</p>
            <h2>{t('municipalities.title')}</h2>
            <p className="ops-page__lede">{t('municipalities.lede')}</p>
          </div>
        </header>
        {error ? (
          <p className="ops-page__error" role="alert">
            {error}
          </p>
        ) : null}
        {loading ? (
          <LoadingState message={t('municipalities.loading')} />
        ) : (
          <section className="ops-stack municipalities-page__list">
            {items.map((item) => (
              <article
                key={item.municipalityId}
                className={`municipalities-page__card${
                  editingId === item.municipalityId ? ' municipalities-page__card--editing' : ''
                }`}
              >
                <div>
                  <h3>{item.name}</h3>
                  <p>{item.description}</p>
                  <p className="ops-page__meta">
                    {item.serviceDomains.join(', ')} · v{item.profileVersion} ·{' '}
                    {item.active ? t('municipalities.active') : t('municipalities.inactive')}
                  </p>
                  {item.departments && item.departments.length > 0 ? (
                    <p className="ops-page__meta">
                      {item.departments.map((department) => department.name).join(', ')}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="municipalities-page__edit"
                  onClick={() => handleEdit(item)}
                >
                  {t('municipalities.edit')}
                </button>
              </article>
            ))}
          </section>
        )}

        <form ref={editFormRef} className="municipalities-page__form" onSubmit={handleSave}>
          <h3>{editingId ? t('municipalities.editTitle') : t('municipalities.createTitle')}</h3>
          <label className="ops-field">
            {t('municipalities.name')}
            <input
              ref={nameInputRef}
              required
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label className="ops-field">
            {t('municipalities.description')}
            <textarea
              required
              minLength={3}
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
            />
          </label>
          <label className="ops-field">
            {t('municipalities.city')}
            <input
              value={form.city}
              onChange={(event) => setForm((current) => ({ ...current, city: event.target.value }))}
            />
          </label>
          <fieldset className="municipalities-page__domains">
            <legend>{t('municipalities.serviceDomains')}</legend>
            {SERVICE_DOMAINS.map((domain) => (
              <label key={domain}>
                <input
                  type="checkbox"
                  checked={form.serviceDomains.includes(domain)}
                  onChange={() =>
                    setForm((current) => ({
                      ...current,
                      serviceDomains: toggleDomain(current.serviceDomains, domain),
                    }))
                  }
                />
                {domain}
              </label>
            ))}
          </fieldset>
          <div className="ops-toolbar">
            <label className="ops-field">
              min lat
              <input
                value={form.minLatitude}
                onChange={(event) =>
                  setForm((current) => ({ ...current, minLatitude: event.target.value }))
                }
              />
            </label>
            <label className="ops-field">
              max lat
              <input
                value={form.maxLatitude}
                onChange={(event) =>
                  setForm((current) => ({ ...current, maxLatitude: event.target.value }))
                }
              />
            </label>
            <label className="ops-field">
              min lon
              <input
                value={form.minLongitude}
                onChange={(event) =>
                  setForm((current) => ({ ...current, minLongitude: event.target.value }))
                }
              />
            </label>
            <label className="ops-field">
              max lon
              <input
                value={form.maxLongitude}
                onChange={(event) =>
                  setForm((current) => ({ ...current, maxLongitude: event.target.value }))
                }
              />
            </label>
          </div>
          <label>
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) =>
                setForm((current) => ({ ...current, active: event.target.checked }))
              }
            />{' '}
            {t('municipalities.active')}
          </label>
          <button type="submit" disabled={saving}>
            {saving ? t('common.loading') : t('common.save')}
          </button>
        </form>

        <form className="municipalities-page__form" onSubmit={handleProvision}>
          <h3>{t('municipalities.adminTitle')}</h3>
          <label className="ops-field">
            {t('municipalities.municipality')}
            <select
              required
              value={adminForm.municipalityId}
              onChange={(event) =>
                setAdminForm((current) => ({ ...current, municipalityId: event.target.value }))
              }
            >
              <option value="">{t('municipalities.selectMunicipality')}</option>
              {items.map((item) => (
                <option key={item.municipalityId} value={item.municipalityId}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label className="ops-field">
            {t('staffAccounts.username')}
            <input
              required
              value={adminForm.username}
              onChange={(event) =>
                setAdminForm((current) => ({ ...current, username: event.target.value }))
              }
            />
          </label>
          <label className="ops-field">
            {t('staffAccounts.name')}
            <input
              required
              value={adminForm.name}
              onChange={(event) =>
                setAdminForm((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="ops-field">
            {t('staffAccounts.email')}
            <input
              required
              type="email"
              value={adminForm.email}
              onChange={(event) =>
                setAdminForm((current) => ({ ...current, email: event.target.value }))
              }
            />
          </label>
          <label className="ops-field">
            {t('staffAccounts.initialPassword')}
            <input
              required
              minLength={8}
              type="password"
              value={adminForm.password}
              onChange={(event) =>
                setAdminForm((current) => ({ ...current, password: event.target.value }))
              }
            />
          </label>
          <button type="submit" disabled={saving}>
            {t('municipalities.provisionAdmin')}
          </button>
        </form>

        <form className="municipalities-page__form" onSubmit={handlePreview}>
          <h3>{t('municipalities.previewTitle')}</h3>
          <div className="ops-toolbar">
            <label className="ops-field">
              lat
              <input
                value={preview.latitude}
                onChange={(event) =>
                  setPreview((current) => ({ ...current, latitude: event.target.value }))
                }
              />
            </label>
            <label className="ops-field">
              lon
              <input
                value={preview.longitude}
                onChange={(event) =>
                  setPreview((current) => ({ ...current, longitude: event.target.value }))
                }
              />
            </label>
            <label className="ops-field">
              {t('municipalities.category')}
              <input
                value={preview.category}
                onChange={(event) =>
                  setPreview((current) => ({ ...current, category: event.target.value }))
                }
              />
            </label>
          </div>
          <button type="submit">{t('municipalities.preview')}</button>
          {preview.result ? <p className="ops-page__meta">{preview.result}</p> : null}
        </form>

        <form className="municipalities-page__form" onSubmit={handleOverride}>
          <h3>{t('municipalities.overrideTitle')}</h3>
          <label className="ops-field">
            {t('municipalities.ticketId')}
            <input
              required
              value={overrideForm.ticketId}
              onChange={(event) =>
                setOverrideForm((current) => ({ ...current, ticketId: event.target.value }))
              }
            />
          </label>
          <label className="ops-field">
            {t('municipalities.municipality')}
            <select
              value={overrideForm.municipalityId}
              onChange={(event) =>
                setOverrideForm((current) => ({ ...current, municipalityId: event.target.value }))
              }
            >
              <option value="">{t('municipalities.unassigned')}</option>
              {selectedOverrideOptions.map((item) => (
                <option key={item.municipalityId} value={item.municipalityId}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={saving}>
            {t('municipalities.override')}
          </button>
        </form>
      </div>
    </DashboardLayout>
  );
}

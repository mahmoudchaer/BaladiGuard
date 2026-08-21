import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import {
  acceptLegal as acceptLegalApi,
  deleteMe,
  exportMe,
  requestOtp,
} from '@/services/citizenAuth';
import { clearDraft, loadDraft } from '@/services/reportDraft';
import type { TicketUpdatesPreference } from '@/types/citizen';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useI18n } from '@/i18n/LocaleProvider';

export function ProfilePage() {
  const { t, locale } = useI18n();
  const auth = useCitizenAuth();
  const navigate = useNavigate();
  const profile = auth.profile!;
  const [name, setName] = useState(profile.fullName ?? '');
  const [email, setEmail] = useState(profile.email ?? '');
  const [ticketUpdates, setTicketUpdates] = useState<TicketUpdatesPreference>(
    profile.notificationPreferences.ticketUpdates,
  );
  const [announcements, setAnnouncements] = useState(profile.notificationPreferences.announcements);
  const [publicNameVisible, setPublicNameVisible] = useState(profile.publicNameVisible);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phoneMode, setPhoneMode] = useState(false);
  const [newPhone, setNewPhone] = useState('');
  const [challenge, setChallenge] = useState('');
  const [phoneCode, setPhoneCode] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState('');

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await auth.updateProfile({
        fullName: name.trim() || null,
        email: email.trim() || null,
        notificationPreferences: { ticketUpdates, announcements },
        publicNameVisible: Boolean(name.trim()) && publicNameVisible,
      });
      setMessage(t('profile.updated'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function beginPhoneChange() {
    setBusy(true);
    setError(null);
    try {
      const result = await requestOtp(newPhone, 'LB', 'CHANGE_PHONE');
      setChallenge(result.challengeId);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.sendFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function finishPhoneChange() {
    setBusy(true);
    setError(null);
    try {
      await auth.updateProfile({
        phone: newPhone,
        region: 'LB',
        phoneChangeChallengeId: challenge,
        phoneChangeCode: phoneCode,
      });
      setMessage(t('profile.phoneUpdated'));
      await auth.logout();
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.phoneFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    const draft = await loadDraft(profile.userId);
    const hasDraft = Boolean(
      draft && (draft.description.trim() || draft.addressText.trim() || draft.imageObjectKey),
    );
    const retain = hasDraft ? window.confirm(t('profile.keepDraft')) : false;
    if (!retain) await clearDraft(profile.userId);
    await auth.logout();
    navigate('/');
  }

  async function handleExport() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const data = await exportMe();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `baladiguard-export-${profile.userId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(t('profile.exportReady'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.exportFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptLegal() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await acceptLegalApi({ acceptLegal: true, locale });
      auth.setProfile(next);
      setMessage(t('profile.legalAccepted'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.legalAcceptFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    const typedOk = deleteConfirm.trim().toUpperCase() === 'DELETE';
    if (!typedOk) {
      const confirmed = window.confirm(t('profile.deleteConfirmPrompt'));
      if (!confirmed) return;
    } else if (!window.confirm(t('profile.deleteConfirmPrompt'))) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteMe();
      await clearDraft(profile.userId);
      auth.setProfile(null);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.deleteFailed'));
      setBusy(false);
    }
  }

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('profile.eyebrow')}</span>
          <h1>{t('profile.title')}</h1>
          <p className="lede">{t('profile.lede')}</p>
        </div>
        <div className="avatar-large" aria-hidden>
          {profile.fullName?.[0]?.toUpperCase() || 'B'}
        </div>
      </div>
      <LanguageSwitcher />

      {profile.legalAcceptanceRequired ? (
        <div className="notice notice-error" role="alert">
          <p style={{ margin: '0 0 0.75rem' }}>{t('profile.legalRequiredBanner')}</p>
          <p style={{ margin: '0 0 0.75rem' }}>
            <Link to="/terms">{t('shell.terms')}</Link>
            {' · '}
            <Link to="/privacy">{t('shell.privacy')}</Link>
            {' · '}
            <Link to="/acceptable-use">{t('shell.acceptableUse')}</Link>
          </p>
          <button
            className="button"
            type="button"
            disabled={busy}
            onClick={() => void handleAcceptLegal()}
          >
            {busy ? t('profile.acceptingLegal') : t('profile.acceptLegal')}
          </button>
        </div>
      ) : null}

      {message ? (
        <div className="notice notice-success" role="status">
          {message}
        </div>
      ) : null}
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      ) : null}

      <form className="settings-card" onSubmit={(event) => void save(event)}>
        <div className="settings-section">
          <h2>{t('profile.identity')}</h2>
          <div className="verified-row">
            <div>
              <span className="field-label">{t('profile.verifiedPhone')}</span>
              <strong>{profile.phone}</strong>
            </div>
            <span className="verified-badge">{t('profile.verified')}</span>
          </div>
          <label className="field-label" htmlFor="name">
            {t('profile.fullName')} <span>{t('common.optional')}</span>
          </label>
          <input
            id="name"
            className="input"
            maxLength={120}
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (!e.target.value.trim()) setPublicNameVisible(false);
            }}
          />
          <label className="field-label" htmlFor="email">
            {t('profile.email')} <span>{t('profile.emailOptional')}</span>
          </label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <p className="helper">{t('profile.emailHelper')}</p>
        </div>
        <div className="settings-section">
          <h2>{t('profile.notifications')}</h2>
          <label className="field-label" htmlFor="updates">
            {t('profile.ticketUpdates')}
          </label>
          <select
            id="updates"
            className="input"
            value={ticketUpdates}
            onChange={(e) => setTicketUpdates(e.target.value as TicketUpdatesPreference)}
          >
            <option value="NONE">{t('profile.none')}</option>
            <option value="SMS">{t('profile.sms')}</option>
            <option value="EMAIL">{t('profile.emailOption')}</option>
            <option value="BOTH">{t('profile.smsAndEmail')}</option>
          </select>
          <label className="toggle-row">
            <span>
              <strong>{t('profile.announcements')}</strong>
              <small>{t('profile.announcementsHint')}</small>
            </span>
            <input
              type="checkbox"
              checked={announcements}
              onChange={(e) => setAnnouncements(e.target.checked)}
            />
          </label>
          <label className="toggle-row">
            <span>
              <strong>{t('profile.showName')}</strong>
              <small>{t('profile.showNameHint')}</small>
            </span>
            <input
              type="checkbox"
              disabled={!name.trim()}
              checked={publicNameVisible}
              onChange={(e) => setPublicNameVisible(e.target.checked)}
            />
          </label>
        </div>
        <button className="button button-large" disabled={busy} type="submit">
          {busy ? t('profile.saving') : t('profile.saveChanges')}
        </button>
      </form>

      <div className="settings-card">
        <button className="setting-action" type="button" onClick={() => setPhoneMode(!phoneMode)}>
          <span>
            <strong>{t('profile.changePhone')}</strong>
            <small>{t('profile.changePhoneHint')}</small>
          </span>
          <span>›</span>
        </button>
        {phoneMode ? (
          <div className="phone-flow">
            <input
              className="input"
              inputMode="tel"
              placeholder={t('profile.newPhone')}
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
            />
            {!challenge ? (
              <button
                className="button"
                disabled={busy || newPhone.length < 6}
                type="button"
                onClick={() => void beginPhoneChange()}
              >
                {t('profile.sendCode')}
              </button>
            ) : (
              <>
                <input
                  className="input otp-input"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="000000"
                  value={phoneCode}
                  onChange={(e) => setPhoneCode(e.target.value.replace(/\D/g, ''))}
                />
                <button
                  className="button"
                  disabled={busy || phoneCode.length !== 6}
                  type="button"
                  onClick={() => void finishPhoneChange()}
                >
                  {t('profile.verifyPhone')}
                </button>
              </>
            )}
          </div>
        ) : null}
        <button
          className="setting-action"
          type="button"
          disabled={busy}
          onClick={() => void handleExport()}
        >
          <span>
            <strong>{t('profile.exportData')}</strong>
            <small>{t('profile.exportDataHint')}</small>
          </span>
          <span>↓</span>
        </button>
        <div className="phone-flow" style={{ padding: '0.75rem 0' }}>
          <label className="field-label" htmlFor="delete-confirm">
            {t('profile.deleteTypeLabel')}
          </label>
          <input
            id="delete-confirm"
            className="input"
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={t('profile.deleteTypePlaceholder')}
            autoComplete="off"
          />
          <button
            className="setting-action danger-action"
            type="button"
            disabled={busy}
            onClick={() => void handleDelete()}
          >
            <span>
              <strong>{t('profile.deleteAccount')}</strong>
              <small>{t('profile.deleteAccountHint')}</small>
            </span>
            <span>!</span>
          </button>
        </div>
        <button
          className="setting-action danger-action"
          type="button"
          onClick={() => void signOut()}
        >
          <span>
            <strong>{t('profile.signOut')}</strong>
            <small>{t('profile.draftsPrivate')}</small>
          </span>
          <span>→</span>
        </button>
      </div>
    </section>
  );
}

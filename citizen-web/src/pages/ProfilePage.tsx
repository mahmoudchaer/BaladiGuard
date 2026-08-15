import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { requestOtp } from '@/services/citizenAuth';
import { clearDraft, loadDraft } from '@/services/reportDraft';
import type { TicketUpdatesPreference } from '@/types/citizen';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { t } from '@/i18n';

export function ProfilePage() {
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
      setMessage('Your profile was updated.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save your profile.');
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
      setError(err instanceof Error ? err.message : 'Unable to send a code.');
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
      setMessage('Phone updated. Please sign in again with your new number.');
      await auth.logout();
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to change your phone.');
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    const draft = await loadDraft(profile.userId);
    const hasDraft = Boolean(
      draft && (draft.description.trim() || draft.addressText.trim() || draft.imageObjectKey),
    );
    const retain = hasDraft
      ? window.confirm(
          'Keep this account’s saved report draft for your next sign-in? Choose Cancel to clear it before signing out.',
        )
      : false;
    if (!retain) await clearDraft(profile.userId);
    await auth.logout();
    navigate('/');
  }

  return (
    <section className="page page-enter narrow-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR ACCOUNT</span>
          <h1>{t('profile.title')}</h1>
          <p className="lede">Control what you share and how the municipality reaches you.</p>
        </div>
        <div className="avatar-large" aria-hidden>
          {profile.fullName?.[0]?.toUpperCase() || 'B'}
        </div>
      </div>
      <LanguageSwitcher />

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
          <h2>Identity</h2>
          <div className="verified-row">
            <div>
              <span className="field-label">Verified phone</span>
              <strong>{profile.phone}</strong>
            </div>
            <span className="verified-badge">✓ Verified</span>
          </div>
          <label className="field-label" htmlFor="name">
            Full name <span>Optional</span>
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
            Email <span>Optional · notifications only</span>
          </label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <p className="helper">Email cannot be used to sign in or recover your account.</p>
        </div>
        <div className="settings-section">
          <h2>Notifications</h2>
          <label className="field-label" htmlFor="updates">
            Ticket updates
          </label>
          <select
            id="updates"
            className="input"
            value={ticketUpdates}
            onChange={(e) => setTicketUpdates(e.target.value as TicketUpdatesPreference)}
          >
            <option value="NONE">None</option>
            <option value="SMS">SMS</option>
            <option value="EMAIL">Email</option>
            <option value="BOTH">SMS and email</option>
          </select>
          <label className="toggle-row">
            <span>
              <strong>Community announcements</strong>
              <small>Occasional civic updates</small>
            </span>
            <input
              type="checkbox"
              checked={announcements}
              onChange={(e) => setAnnouncements(e.target.checked)}
            />
          </label>
          <label className="toggle-row">
            <span>
              <strong>Show my name publicly</strong>
              <small>Otherwise reports say “Community member”</small>
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
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <div className="settings-card">
        <button className="setting-action" type="button" onClick={() => setPhoneMode(!phoneMode)}>
          <span>
            <strong>Change verified phone</strong>
            <small>Requires a new OTP</small>
          </span>
          <span>›</span>
        </button>
        {phoneMode ? (
          <div className="phone-flow">
            <input
              className="input"
              inputMode="tel"
              placeholder="New phone number"
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
                Send verification code
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
                  Verify new phone
                </button>
              </>
            )}
          </div>
        ) : null}
        <button
          className="setting-action danger-action"
          type="button"
          onClick={() => void signOut()}
        >
          <span>
            <strong>Sign out</strong>
            <small>Drafts remain private to this account</small>
          </span>
          <span>→</span>
        </button>
      </div>
    </section>
  );
}

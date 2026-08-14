import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { sanitizeReturnTo } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { ApiError } from '@/services/api';
import { requestOtp } from '@/services/citizenAuth';

type Step = 'phone' | 'code';

export function LoginPage() {
  const auth = useCitizenAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const returnTo = sanitizeReturnTo(params.get('returnTo'));
  const [step, setStep] = useState<Step>('phone');
  const [region, setRegion] = useState('LB');
  const [phone, setPhone] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [code, setCode] = useState('');
  const [expiresAt, setExpiresAt] = useState(0);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (step !== 'code') return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [step]);

  const remaining = useMemo(
    () => Math.max(0, Math.ceil((expiresAt - now) / 1000)),
    [expiresAt, now],
  );

  async function sendCode(event?: FormEvent) {
    event?.preventDefault();
    if (phone.trim().length < 6) {
      setError('Enter a valid phone number.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await requestOtp(phone.trim(), region);
      setChallengeId(result.challengeId);
      setExpiresAt(Date.now() + result.expiresIn * 1000);
      setNow(Date.now());
      setStep('code');
      setCode('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send a code.');
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError('Enter the six-digit verification code.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.applyOtp(challengeId, code);
      navigate(returnTo, { replace: true });
    } catch (err) {
      const api = err instanceof ApiError ? err : null;
      if (api?.code === 'INVALID_OTP') setError('That code is incorrect. Try again.');
      else if (api?.code === 'OTP_EXPIRED') setError('That code expired. Request a new one.');
      else setError(err instanceof Error ? err.message : 'Unable to verify that code.');
    } finally {
      setBusy(false);
    }
  }

  if (!auth.isLoading && auth.isAuthenticated) return <Navigate replace to={returnTo} />;

  return (
    <section className="auth-layout page-enter">
      <div className="auth-hero" aria-hidden="true">
        <div className="hero-orbit">
          <span>✓</span>
        </div>
        <p>Private by design</p>
      </div>
      <div className="auth-card glass-card">
        <span className="eyebrow">CITIZEN ACCESS</span>
        <h1 aria-label={step === 'phone' ? 'Sign in' : undefined}>
          {step === 'phone' ? 'Your city, within reach.' : 'Check your phone.'}
        </h1>
        <p className="lede">
          {step === 'phone'
            ? 'Sign in or create an account with a verified phone number. No password required.'
            : `We sent a six-digit code to ${phone}.`}
        </p>

        {error ? (
          <div className="notice notice-error" role="alert">
            {error}
          </div>
        ) : null}

        {step === 'phone' ? (
          <form className="form-stack" onSubmit={(event) => void sendCode(event)}>
            <label className="field-label" htmlFor="region">
              Country
            </label>
            <select
              id="region"
              className="input"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              <option value="LB">Lebanon (+961)</option>
              <option value="US">United States (+1)</option>
              <option value="FR">France (+33)</option>
              <option value="GB">United Kingdom (+44)</option>
            </select>
            <label className="field-label" htmlFor="phone">
              Phone number
            </label>
            <input
              id="phone"
              className="input"
              inputMode="tel"
              autoComplete="tel"
              placeholder="70 123 456"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoFocus
            />
            <button className="button button-large" disabled={busy} type="submit">
              {busy ? 'Sending…' : 'Continue'} <span aria-hidden>→</span>
            </button>
          </form>
        ) : (
          <form className="form-stack" onSubmit={(event) => void verify(event)}>
            <label className="field-label" htmlFor="otp">
              Verification code
            </label>
            <input
              id="otp"
              className="input otp-input"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              autoFocus
            />
            <button
              className="button button-large"
              disabled={busy || code.length !== 6}
              type="submit"
            >
              {busy ? 'Verifying…' : 'Verify and continue'}
            </button>
            <div className="inline-actions">
              <button className="text-button" type="button" onClick={() => setStep('phone')}>
                Change number
              </button>
              <button
                className="text-button"
                type="button"
                disabled={busy || remaining > 0}
                onClick={() => void sendCode()}
              >
                {remaining > 0 ? `Resend in ${remaining}s` : 'Resend code'}
              </button>
            </div>
          </form>
        )}
        <p className="privacy-note">
          Your phone verifies account ownership. Your name and email stay optional.
        </p>
      </div>
    </section>
  );
}

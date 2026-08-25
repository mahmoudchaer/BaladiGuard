import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { sanitizeReturnTo } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { ApiError } from '@/services/api';
import { requestOtp } from '@/services/citizenAuth';
import { CountryRegionSelect } from '@/components/CountryRegionSelect';
import { useI18n } from '@/i18n/LocaleProvider';
import { consumePhoneChangedNotice } from '@/services/phoneChangeNotice';

type Step = 'phone' | 'code';

export function LoginPage() {
  const auth = useCitizenAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const returnTo = sanitizeReturnTo(params.get('returnTo'));
  const [phoneChanged] = useState(consumePhoneChangedNotice);
  const [step, setStep] = useState<Step>('phone');
  const [region, setRegion] = useState('LB');
  const [phone, setPhone] = useState('');
  const [challengeId, setChallengeId] = useState('');
  const [deliveryChannel, setDeliveryChannel] = useState<'sms' | 'whatsapp' | 'dev' | undefined>();
  const [code, setCode] = useState('');
  const [acceptLegal, setAcceptLegal] = useState(false);
  const [expiresAt, setExpiresAt] = useState(0);
  const [now, setNow] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t, locale } = useI18n();

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
      setError(t('auth.invalidPhone'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await requestOtp(phone.trim(), region);
      setChallengeId(result.challengeId);
      setDeliveryChannel(result.deliveryChannel);
      setExpiresAt(Date.now() + result.expiresIn * 1000);
      setNow(Date.now());
      setStep('code');
      setCode('');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('auth.sendFailed'));
    } finally {
      setBusy(false);
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError(t('auth.invalidCode'));
      return;
    }
    if (!acceptLegal) {
      setError(t('auth.legalRequired'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.applyOtp(challengeId, code, { acceptLegal: true, legalLocale: locale });
      navigate(returnTo, { replace: true });
    } catch (err) {
      const api = err instanceof ApiError ? err : null;
      if (api?.code === 'INVALID_OTP') setError(t('auth.incorrect'));
      else if (api?.code === 'OTP_EXPIRED') setError(t('auth.expired'));
      else if (api?.code === 'LEGAL_ACCEPTANCE_REQUIRED') setError(t('auth.legalRequired'));
      else setError(err instanceof Error ? err.message : t('auth.verifyFailed'));
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
        <p>{t('auth.hero')}</p>
      </div>
      <div className="auth-card glass-card">
        <span className="eyebrow">{t('auth.eyebrow')}</span>
        <h1 aria-label={step === 'phone' ? t('common.signIn') : undefined}>
          {step === 'phone' ? t('auth.phoneTitle') : t('auth.otpTitle')}
        </h1>
        <p className="lede">
          {step === 'phone'
            ? t('auth.phoneLede')
            : t(
                deliveryChannel === 'whatsapp'
                  ? 'auth.otpLedeWhatsapp'
                  : deliveryChannel === 'dev'
                    ? 'auth.otpLedeDev'
                    : deliveryChannel === 'sms'
                      ? 'auth.otpLedeSms'
                      : 'auth.otpLede',
                { phone },
              )}
        </p>

        {phoneChanged && step === 'phone' ? (
          <div className="notice notice-success" role="status">
            {t('auth.phoneChanged')}
          </div>
        ) : null}

        {error ? (
          <div className="notice notice-error" role="alert">
            {error}
          </div>
        ) : null}

        {step === 'phone' ? (
          <form className="form-stack" onSubmit={(event) => void sendCode(event)}>
            <label className="field-label" htmlFor="region">
              {t('auth.country')}
            </label>
            <CountryRegionSelect id="region" value={region} onChange={setRegion} />
            <label className="field-label" htmlFor="phone">
              {t('auth.phone')}
            </label>
            <input
              id="phone"
              className="input"
              inputMode="tel"
              autoComplete="tel"
              placeholder={t('auth.phonePlaceholder')}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoFocus
            />
            <button className="button button-large" disabled={busy} type="submit">
              {busy ? t('auth.sending') : t('auth.continue')} <span aria-hidden>→</span>
            </button>
          </form>
        ) : (
          <form className="form-stack" onSubmit={(event) => void verify(event)}>
            <label className="field-label" htmlFor="otp">
              {t('auth.code')}
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
            <label className="legal-consent" htmlFor="accept-legal">
              <input
                id="accept-legal"
                type="checkbox"
                checked={acceptLegal}
                onChange={(e) => setAcceptLegal(e.target.checked)}
                required
                aria-required="true"
              />
              <span className="legal-consent__copy">
                {t('auth.legalAgreePrefix')} <Link to="/terms">{t('shell.terms')}</Link>
                {t('auth.legalAgreeJoin1')}
                <Link to="/privacy">{t('shell.privacy')}</Link>
                {t('auth.legalAgreeJoin2')}
                <Link to="/acceptable-use">{t('shell.acceptableUse')}</Link>
                {t('auth.legalAgreeSuffix')}
              </span>
            </label>
            <button
              className="button button-large"
              disabled={busy || code.length !== 6 || !acceptLegal}
              type="submit"
            >
              {busy ? t('auth.verifying') : t('auth.verify')}
            </button>
            <div className="inline-actions">
              <button className="text-button" type="button" onClick={() => setStep('phone')}>
                {t('auth.changeNumber')}
              </button>
              <button
                className="text-button"
                type="button"
                disabled={busy || remaining > 0}
                onClick={() => void sendCode()}
              >
                {remaining > 0 ? t('auth.resendIn', { seconds: remaining }) : t('auth.resend')}
              </button>
            </div>
          </form>
        )}
        <p className="privacy-note">{t('auth.privacyNote')}</p>
      </div>
    </section>
  );
}

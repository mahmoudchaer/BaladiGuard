import { type FormEvent, useId, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BrandMark } from '@/components/BrandMark';
import { useI18n } from '@/i18n/LocaleProvider';
import { requestStaffPasswordReset } from '@/services/auth';
import '@/components/BrandMark.css';
import './LoginPage.css';

export function ForgotPasswordPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const errorId = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    try {
      const result = await requestStaffPasswordReset(username);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setMessage(result.message);
      navigate('/reset-password', {
        replace: false,
        state: { username: username.trim(), notice: result.message },
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="forgot-title">
        <div className="login-panel__brand">
          <span className="login-panel__logo" aria-hidden="true">
            <BrandMark size={24} />
          </span>
          <div>
            <p className="login-panel__eyebrow">{t('login.eyebrow')}</p>
            <h1 id="forgot-title">{t('login.forgotTitle')}</h1>
          </div>
        </div>

        <p className="login-form__hint">{t('login.forgotHint')}</p>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-form__field">
            <span>{t('login.username')}</span>
            <input
              autoComplete="username"
              name="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              disabled={isSubmitting}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? errorId : undefined}
            />
          </label>

          {error && (
            <p className="login-form__error" role="alert" id={errorId}>
              {error}
            </p>
          )}
          {message && (
            <p className="login-form__success" role="status">
              {message}
            </p>
          )}

          <button className="login-form__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t('login.sending') : t('login.requestCode')}
          </button>
        </form>

        <p className="login-form__footer">
          <Link to="/reset-password">{t('login.haveCode')}</Link>
          {' · '}
          <Link to="/login">{t('login.backToSignIn')}</Link>
        </p>
      </section>
    </main>
  );
}

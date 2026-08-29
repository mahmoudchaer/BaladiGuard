import { type FormEvent, useId, useState } from 'react';
import { Link, Navigate, type Location, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { homePathForRole } from '@/services/auth';
import { BrandMark } from '@/components/BrandMark';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useI18n } from '@/i18n/LocaleProvider';
import '@/components/BrandMark.css';
import './LoginPage.css';

type LoginLocationState = {
  from?: Pick<Location, 'pathname' | 'search' | 'hash'>;
  resetSuccess?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login, session } = useStaffAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const errorId = useId();
  const successId = useId();
  const { t } = useI18n();

  const state = location.state as LoginLocationState | null;
  const returnTo = state?.from
    ? `${state.from.pathname}${state.from.search}${state.from.hash}`
    : '/';
  const resetSuccess = state?.resetSuccess;

  const home = homePathForRole(session?.role);
  if (isAuthenticated) {
    const destination =
      session?.role === 'developer_operator'
        ? returnTo.startsWith('/ops')
          ? returnTo
          : home
        : returnTo.startsWith('/ops')
          ? home
          : returnTo;
    return <Navigate to={destination} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedUsername = username.trim();
    if (!trimmedUsername || !password) {
      setError(t('login.missingCredentials'));
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await login(trimmedUsername, password);

      if (!result.ok) {
        setPassword('');
        setError(result.error);
        return;
      }

      navigate(
        result.session.role === 'developer_operator'
          ? returnTo.startsWith('/ops')
            ? returnTo
            : '/ops'
          : returnTo.startsWith('/ops')
            ? '/'
            : returnTo,
        { replace: true },
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel__brand">
          <span className="login-panel__logo" aria-hidden="true">
            <BrandMark size={24} />
          </span>
          <div>
            <p className="login-panel__eyebrow">{t('login.eyebrow')}</p>
            <h1 id="login-title">{t('login.title')}</h1>
          </div>
        </div>

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
              aria-describedby={error ? errorId : resetSuccess ? successId : undefined}
            />
          </label>

          <label className="login-form__field">
            <span>{t('login.password')}</span>
            <span className="login-form__password-wrap">
              <input
                autoComplete="current-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                disabled={isSubmitting}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? errorId : undefined}
              />
              <button
                type="button"
                className="login-form__toggle"
                onClick={() => setShowPassword((value) => !value)}
                aria-pressed={showPassword}
              >
                {showPassword ? t('login.hide') : t('login.show')}
              </button>
            </span>
          </label>

          {resetSuccess && (
            <p className="login-form__success" role="status" id={successId}>
              {resetSuccess}
            </p>
          )}

          {error && (
            <p className="login-form__error" role="alert" id={errorId}>
              {error}
            </p>
          )}

          <button className="login-form__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t('login.submitting') : t('login.submit')}
          </button>
        </form>

        <LanguageSwitcher />

        <p className="login-form__footer">
          <Link to="/forgot-password">{t('login.forgotPassword')}</Link>
        </p>
      </section>
    </main>
  );
}

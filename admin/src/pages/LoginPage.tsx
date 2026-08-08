import { type FormEvent, useId, useState } from 'react';
import { Link, Navigate, type Location, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import { BrandMark } from '@/components/BrandMark';
import '@/components/BrandMark.css';
import './LoginPage.css';

type LoginLocationState = {
  from?: Pick<Location, 'pathname' | 'search' | 'hash'>;
  resetSuccess?: string;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login } = useStaffAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const errorId = useId();
  const successId = useId();

  const state = location.state as LoginLocationState | null;
  const returnTo = state?.from
    ? `${state.from.pathname}${state.from.search}${state.from.hash}`
    : '/';
  const resetSuccess = state?.resetSuccess;

  if (isAuthenticated) {
    return <Navigate to={returnTo} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const result = await login(username, password);

      if (!result.ok) {
        setPassword('');
        setError(result.error);
        return;
      }

      navigate(returnTo, { replace: true });
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
            <p className="login-panel__eyebrow">Municipal Staff Portal</p>
            <h1 id="login-title">BaladiGuard staff login</h1>
          </div>
        </div>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <label className="login-form__field">
            <span>Username</span>
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
            <span>Password</span>
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
                {showPassword ? 'Hide' : 'Show'}
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
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="login-form__footer">
          <Link to="/forgot-password">Forgot password?</Link>
        </p>
      </section>
    </main>
  );
}

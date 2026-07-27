import { type FormEvent, useState } from 'react';
import { Navigate, type Location, useLocation, useNavigate } from 'react-router-dom';
import { useStaffAuth } from '@/auth/useStaffAuth';
import './LoginPage.css';

type LoginLocationState = {
  from?: Pick<Location, 'pathname' | 'search' | 'hash'>;
};

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, login } = useStaffAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  const state = location.state as LoginLocationState | null;
  const returnTo = state?.from
    ? `${state.from.pathname}${state.from.search}${state.from.hash}`
    : '/';

  if (isAuthenticated) {
    return <Navigate to={returnTo} replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const result = login(username, password);

    if (!result.ok) {
      setPassword('');
      setError(result.error);
      return;
    }

    navigate(returnTo, { replace: true });
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-panel__brand">
          <span className="login-panel__logo" aria-hidden="true">
            BG
          </span>
          <div>
            <p className="login-panel__eyebrow">Municipal Staff Portal</p>
            <h1 id="login-title">BaladiGuard staff login</h1>
          </div>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-form__field">
            <span>Username</span>
            <input
              autoComplete="username"
              name="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </label>

          <label className="login-form__field">
            <span>Password</span>
            <input
              autoComplete="current-password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error && (
            <p className="login-form__error" role="alert">
              {error}
            </p>
          )}

          <button className="login-form__submit" type="submit">
            Sign in
          </button>
        </form>
      </section>
    </main>
  );
}

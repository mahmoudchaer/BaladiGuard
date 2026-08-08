import { type FormEvent, useId, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { BrandMark } from '@/components/BrandMark';
import { confirmStaffPasswordReset } from '@/services/auth';
import '@/components/BrandMark.css';
import './LoginPage.css';

type ResetLocationState = {
  username?: string;
  notice?: string;
};

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const incoming = (location.state as ResetLocationState | null) ?? null;
  const [username, setUsername] = useState(incoming?.username ?? '');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice] = useState<string | null>(incoming?.notice ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const errorId = useId();
  const noticeId = useId();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await confirmStaffPasswordReset({
        username,
        code,
        newPassword,
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      navigate('/login', { replace: true, state: { resetSuccess: result.message } });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="reset-title">
        <div className="login-panel__brand">
          <span className="login-panel__logo" aria-hidden="true">
            <BrandMark size={24} />
          </span>
          <div>
            <p className="login-panel__eyebrow">Municipal Staff Portal</p>
            <h1 id="reset-title">Reset password</h1>
          </div>
        </div>

        {notice && (
          <p className="login-form__success" role="status" id={noticeId}>
            {notice}
          </p>
        )}

        <p className="login-form__hint">
          Enter the reset code you received, then choose a new password (at least 8 characters).
        </p>

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
              disabled={isSubmitting}
            />
          </label>

          <label className="login-form__field">
            <span>Reset code</span>
            <input
              autoComplete="one-time-code"
              name="code"
              inputMode="numeric"
              type="text"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              required
              disabled={isSubmitting}
              aria-describedby={notice ? noticeId : undefined}
            />
          </label>

          <label className="login-form__field">
            <span>New password</span>
            <span className="login-form__password-wrap">
              <input
                autoComplete="new-password"
                name="newPassword"
                type={showPassword ? 'text' : 'password'}
                minLength={8}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
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

          {error && (
            <p className="login-form__error" role="alert" id={errorId}>
              {error}
            </p>
          )}

          <button className="login-form__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Updating…' : 'Update password'}
          </button>
        </form>

        <p className="login-form__footer">
          <Link to="/forgot-password">Request a new code</Link>
          {' · '}
          <Link to="/login">Back to sign in</Link>
        </p>
      </section>
    </main>
  );
}

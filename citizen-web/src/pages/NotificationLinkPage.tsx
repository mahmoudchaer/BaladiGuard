/**
 * Landing surface for notification deep links `/t/{trackingCode}` (issues #257 / #265).
 *
 * - Malformed codes → safe fallback (no ownership language).
 * - Logged out → track (possession) or sign-in with returnTo.
 * - Logged in → citizen-safe track lookup for the code.
 * Invalid / inaccessible outcomes use track-form error text only (no “not yours”).
 */

import { Link, Navigate, useParams } from 'react-router-dom';
import { loginPath } from '@/auth/returnTo';
import { useCitizenAuth } from '@/auth/CitizenAuthContext';
import { isValidTrackingCode, normalizeTrackingCode } from '@/utils/trackingCode';

export function NotificationLinkPage() {
  const { code } = useParams<{ code?: string }>();
  const { isAuthenticated, isLoading } = useCitizenAuth();
  const normalized = normalizeTrackingCode(code ?? '');
  const valid = isValidTrackingCode(normalized);
  const trackHref = valid ? `/track?trackingCode=${encodeURIComponent(normalized)}` : '/track';
  const deepPath = `/t/${normalized}`;

  if (isLoading || (valid && isAuthenticated)) {
    if (!isLoading && valid && isAuthenticated) {
      return <Navigate replace to={trackHref} />;
    }
    return (
      <section className="page" aria-label="Opening report" role="status">
        <p className="lede">{valid ? 'Opening report status…' : 'Restoring your session…'}</p>
      </section>
    );
  }

  if (!valid) {
    return (
      <section className="page" data-testid="notification-link-invalid">
        <h1>Link cannot be used</h1>
        <p className="lede">
          This link is missing a valid tracking code. You can still look up a report with a code
          from your receipt or SMS, or return home.
        </p>
        <div className="button-row">
          <Link className="button" to="/track" aria-label="Track a report">
            Track a report
          </Link>
          <Link className="button button-secondary" to="/">
            Home
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="page" data-testid="notification-link-guest">
      <h1>Continue with this report</h1>
      <p className="lede" role="status">
        Sign in is optional. Tracking only needs a valid code from your notification. Status is
        shared when the code is valid—same as the track screen.
      </p>
      <p>
        Tracking code from the link: <strong>{normalized}</strong>. Choose how to continue.
      </p>
      <div className="button-row">
        <Link className="button" to={trackHref} aria-label="Track with this code">
          Track with this code
        </Link>
        <Link
          className="button button-secondary"
          to={loginPath(deepPath)}
          aria-label="Sign in to continue"
        >
          Sign in
        </Link>
      </div>
    </section>
  );
}

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
import { t } from '@/i18n';

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
      <section className="page" aria-label={t('track.openingA11y')} role="status">
        <p className="lede">{valid ? t('track.opening') : t('track.restoring')}</p>
      </section>
    );
  }

  if (!valid) {
    return (
      <section className="page" data-testid="notification-link-invalid">
        <h1>{t('track.invalidLinkTitle')}</h1>
        <p className="lede">{t('track.invalidLinkBody')}</p>
        <div className="button-row">
          <Link className="button" to="/track" aria-label={t('track.title')}>
            {t('track.title')}
          </Link>
          <Link className="button button-secondary" to="/">
            {t('shell.home')}
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="page" data-testid="notification-link-guest">
      <h1>{t('track.continueTitle')}</h1>
      <p className="lede" role="status">
        {t('track.optionalSignIn')}
      </p>
      <p>{t('track.codeFromLink', { code: normalized })}</p>
      <div className="button-row">
        <Link className="button" to={trackHref} aria-label={t('track.trackWithCode')}>
          {t('track.trackWithCode')}
        </Link>
        <Link
          className="button button-secondary"
          to={loginPath(deepPath)}
          aria-label={t('track.signInToContinue')}
        >
          {t('common.signIn')}
        </Link>
      </div>
    </section>
  );
}

/**
 * Helpers for login return paths after OTP authentication.
 */

export function sanitizeReturnTo(returnTo: string | string[] | undefined | null): string {
  const raw = Array.isArray(returnTo) ? returnTo[0] : returnTo;
  if (!raw || typeof raw !== 'string') {
    return '/';
  }

  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    decoded = raw;
  }

  if (!decoded.startsWith('/') || decoded.startsWith('//')) {
    return '/';
  }

  const pathOnly = decoded.split('?')[0] ?? '/';
  if (
    pathOnly === '/' ||
    pathOnly.startsWith('/report') ||
    pathOnly.startsWith('/track') ||
    pathOnly.startsWith('/profile') ||
    pathOnly.startsWith('/history') ||
    // Notification deep links (issue #257): `/t/{trackingCode}` only.
    /^\/t\/[A-Za-z0-9]+$/.test(pathOnly)
  ) {
    return pathOnly;
  }

  return '/';
}

export function buildLoginHref(returnTo?: string | null): string {
  const safe = sanitizeReturnTo(returnTo ?? null);
  if (safe === '/') {
    return '/login';
  }
  return `/login?returnTo=${encodeURIComponent(safe)}`;
}

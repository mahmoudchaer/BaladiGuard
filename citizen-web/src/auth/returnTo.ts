const ALLOWED_PATHS = new Set([
  '/',
  '/report',
  '/track',
  '/profile',
  '/history',
  '/reports',
  '/map',
  '/privacy',
]);

const SAFE_QUERY = /^[a-zA-Z0-9=_&%.-]*$/;
const NOTIFICATION_PATH = /^\/t\/[A-Za-z0-9]+$/;
const PUBLIC_DETAIL_PATH = /^\/public\/[A-Za-z0-9-]+$/;

function decodeReturnTo(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function sanitizeReturnTo(value: string | null | undefined): string {
  if (!value) {
    return '/';
  }

  const decoded = decodeReturnTo(value);
  if (
    !decoded.startsWith('/') ||
    decoded.startsWith('//') ||
    decoded.startsWith('/login') ||
    decoded.includes('..') ||
    decoded.includes('\\')
  ) {
    return '/';
  }

  const [pathOnly = '/', ...queryParts] = decoded.split('?');
  const allowed =
    ALLOWED_PATHS.has(pathOnly) ||
    NOTIFICATION_PATH.test(pathOnly) ||
    PUBLIC_DETAIL_PATH.test(pathOnly);
  if (!allowed) {
    return '/';
  }

  const query = queryParts.join('?');
  if (!query || !SAFE_QUERY.test(query)) {
    return pathOnly;
  }
  return `${pathOnly}?${query}`;
}

export function loginPath(returnTo: string): string {
  return `/login?returnTo=${encodeURIComponent(sanitizeReturnTo(returnTo))}`;
}

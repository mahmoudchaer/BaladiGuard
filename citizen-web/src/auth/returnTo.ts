const SAFE_PATH = /^\/[a-zA-Z0-9/_?=&%.-]*$/;

export function sanitizeReturnTo(value: string | null | undefined): string {
  if (!value || !SAFE_PATH.test(value) || value.startsWith('//') || value.startsWith('/login')) {
    return '/';
  }
  return value;
}

export function loginPath(returnTo: string): string {
  return `/login?returnTo=${encodeURIComponent(sanitizeReturnTo(returnTo))}`;
}

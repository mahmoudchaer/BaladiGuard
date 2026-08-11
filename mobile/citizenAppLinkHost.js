/**
 * Resolve the HTTPS host claimed for notification Universal / App Links (#257).
 * Shared by Expo app.config.js (Node) and unit tests.
 */

/**
 * @param {NodeJS.ProcessEnv | Record<string, string | undefined>} [env]
 * @returns {string}
 */
function resolveCitizenAppLinkHost(env = process.env) {
  const raw = (
    env.EXPO_PUBLIC_CITIZEN_APP_HOST ||
    env.EXPO_PUBLIC_CITIZEN_APP_BASE_URL ||
    'app.baladiguard.example'
  )
    .trim()
    .replace(/\/+$/, '');

  if (!raw) {
    return 'app.baladiguard.example';
  }

  try {
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw)) {
      const host = new URL(raw).hostname;
      if (host) {
        return host.toLowerCase();
      }
    }
  } catch {
    // fall through
  }

  const hostOnly = raw.replace(/^\/+/, '').split('/')[0].split('?')[0].split('#')[0];
  return (hostOnly || 'app.baladiguard.example').toLowerCase();
}

module.exports = { resolveCitizenAppLinkHost };

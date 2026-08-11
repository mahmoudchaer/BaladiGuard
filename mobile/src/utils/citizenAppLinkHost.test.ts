import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { resolveCitizenAppLinkHost } = require('../../citizenAppLinkHost.js') as {
  resolveCitizenAppLinkHost: (
    env?: NodeJS.ProcessEnv | Record<string, string | undefined>,
  ) => string;
};

describe('resolveCitizenAppLinkHost', () => {
  it('defaults to the documented placeholder host', () => {
    expect(resolveCitizenAppLinkHost({})).toBe('app.baladiguard.example');
  });

  it('accepts a bare hostname', () => {
    expect(resolveCitizenAppLinkHost({ EXPO_PUBLIC_CITIZEN_APP_HOST: 'links.example.org' })).toBe(
      'links.example.org',
    );
  });

  it('parses host from EXPO_PUBLIC_CITIZEN_APP_BASE_URL', () => {
    expect(
      resolveCitizenAppLinkHost({
        EXPO_PUBLIC_CITIZEN_APP_BASE_URL: 'https://App.Example.com/path/',
      }),
    ).toBe('app.example.com');
  });

  it('prefers explicit HOST over BASE_URL', () => {
    expect(
      resolveCitizenAppLinkHost({
        EXPO_PUBLIC_CITIZEN_APP_HOST: 'a.example',
        EXPO_PUBLIC_CITIZEN_APP_BASE_URL: 'https://b.example',
      }),
    ).toBe('a.example');
  });
});

import { afterEach, vi } from 'vitest';

import { __resetExpoRouterMock } from '@/test/mocks/expo-router';
import { __resetFileSystemMock } from '@/test/mocks/expo-file-system';
import { __resetSecureStoreMock } from '@/test/mocks/expo-secure-store';

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
(globalThis as typeof globalThis & { __DEV__: boolean }).__DEV__ = true;

afterEach(() => {
  vi.unstubAllGlobals();
  __resetExpoRouterMock();
  __resetSecureStoreMock();
  __resetFileSystemMock();
});

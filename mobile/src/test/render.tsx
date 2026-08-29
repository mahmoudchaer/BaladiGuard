import React, { type ReactElement, type ReactNode } from 'react';
import { act, create, type TestRendererOptions } from 'react-test-renderer';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { CitizenAuthProvider } from '@/auth';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import { theme } from '@/theme';

function TestProviders({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>
        <LocaleProvider>
          <CitizenAuthProvider>{children}</CitizenAuthProvider>
        </LocaleProvider>
      </PaperProvider>
    </SafeAreaProvider>
  );
}

export function renderWithProviders(ui: ReactElement, options?: TestRendererOptions) {
  let screen: ReturnType<typeof create> | undefined;

  act(() => {
    screen = create(<TestProviders>{ui}</TestProviders>, options);
  });

  return screen as ReturnType<typeof create>;
}

export async function renderWithProvidersAsync(ui: ReactElement, options?: TestRendererOptions) {
  let screen: ReturnType<typeof create> | undefined;

  await act(async () => {
    screen = create(<TestProviders>{ui}</TestProviders>, options);
  });

  // Flush CitizenAuthProvider restoreSession (SecureStore + optional /me).
  for (let i = 0; i < 5; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }

  return screen as ReturnType<typeof create>;
}

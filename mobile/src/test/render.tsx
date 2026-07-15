import React, { type ReactElement, type ReactNode } from 'react';
import { act, create, type TestRendererOptions } from 'react-test-renderer';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { theme } from '@/theme';

function TestProviders({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider>
      <PaperProvider theme={theme}>{children}</PaperProvider>
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

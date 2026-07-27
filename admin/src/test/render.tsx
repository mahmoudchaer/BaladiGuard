import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { StaffAuthProvider } from '@/auth/StaffAuthContext';

type TestRenderOptions = RenderOptions & {
  route?: string;
};

export function renderWithProviders(ui: ReactElement, options: TestRenderOptions = {}) {
  const { route = '/', ...renderOptions } = options;
  window.history.pushState({}, 'Test page', route);

  return render(ui, {
    wrapper: ({ children }) => (
      <StaffAuthProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </StaffAuthProvider>
    ),
    ...renderOptions,
  });
}

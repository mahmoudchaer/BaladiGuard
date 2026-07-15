import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement } from 'react';
import { BrowserRouter } from 'react-router-dom';

type TestRenderOptions = RenderOptions & {
  route?: string;
};

export function renderWithProviders(ui: ReactElement, options: TestRenderOptions = {}) {
  const { route = '/', ...renderOptions } = options;
  window.history.pushState({}, 'Test page', route);

  return render(ui, {
    wrapper: BrowserRouter,
    ...renderOptions,
  });
}

import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DESKTOP_MIN_PX, TABLET_MIN_PX, TOUCH_TARGET_PX } from '@/a11y/tokens';
import { installControlledBackend, renderApp } from '@/e2e/harness';

vi.mock('@/components/PublicReportsMap', () => ({
  PublicReportsMap: () => null,
}));

describe('critical-flow accessibility and responsive contracts', () => {
  beforeEach(() => {
    installControlledBackend(false);
  });

  it('exposes skip link, landmarks, and a single page heading', async () => {
    renderApp('/');
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute(
      'href',
      '#main-content',
    );
    expect(document.getElementById('main-content')).toBeTruthy();
    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  });

  it('names login fields for keyboard and screen-reader use', async () => {
    renderApp('/login');
    expect(await screen.findByLabelText('Phone number')).toBeInTheDocument();
    expect(screen.getByLabelText('Country')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Continue/ })).toBeEnabled();
  });

  it('documents agreed phone, tablet, and desktop breakpoints plus 44px targets', () => {
    expect(TOUCH_TARGET_PX).toBe(44);
    expect(TABLET_MIN_PX).toBe(768);
    expect(DESKTOP_MIN_PX).toBe(1024);
  });
});

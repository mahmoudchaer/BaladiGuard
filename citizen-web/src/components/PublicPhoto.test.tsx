import type { ReactElement } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PublicPhoto } from '@/components/PublicPhoto';
import { LocaleProvider } from '@/i18n/LocaleProvider';

function renderPhoto(ui: ReactElement) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe('PublicPhoto', () => {
  it('fails closed to a placeholder when photoUrl is missing', () => {
    renderPhoto(<PublicPhoto photoUrl={null} alt="Report photo" />);
    expect(screen.getByLabelText('No public photo available')).toHaveTextContent(
      'Photo unavailable',
    );
  });

  it('renders an image when a public URL is present', () => {
    renderPhoto(<PublicPhoto photoUrl="https://cdn.example/p.jpg" alt="Report photo" />);
    expect(screen.getByRole('img', { name: 'Report photo' })).toHaveAttribute(
      'src',
      'https://cdn.example/p.jpg',
    );
  });
});

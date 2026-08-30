import { act, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { TicketMap } from '@/components/TicketMap';
import { setLocale, t, type AppLocale } from '@/i18n';
import { renderWithProviders } from '@/test/render';

vi.mock('leaflet', () => ({
  default: {
    divIcon: () => ({}),
    latLngBounds: () => ({}),
  },
}));

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children?: ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: ({ url }: { url?: string }) => <div data-testid="tile-layer" data-url={url} />,
  Marker: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  CircleMarker: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Popup: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  ZoomControl: () => null,
  useMap: () => ({
    setView: () => undefined,
    fitBounds: () => undefined,
    getZoom: () => 12,
    getBounds: () => ({
      getNorth: () => 34,
      getSouth: () => 33,
      getEast: () => 36,
      getWest: () => 35,
    }),
  }),
  useMapEvents: () => null,
}));

const LOCALES: AppLocale[] = ['en', 'ar', 'fr'];

describe('TicketMap localization', () => {
  it('localizes the empty detail canvas in en, ar, and fr', async () => {
    renderWithProviders(<TicketMap variant="detail" tickets={[]} />);

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByText(t('map.emptyCoordinates'))).toBeInTheDocument();
    }
  });

  it('localizes overview legend, overlay, and cluster chrome in ar/fr', async () => {
    renderWithProviders(
      <TicketMap
        markers={[]}
        clusters={[{ id: 'c1', latitude: 33.9, longitude: 35.48, count: 4 }]}
        truncated
      />,
    );

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByLabelText(t('map.legend'))).toBeInTheDocument();
      expect(screen.getByText(t('map.layers'))).toBeInTheDocument();
      expect(screen.getByLabelText(t('map.colorBy'))).toBeInTheDocument();
      expect(screen.getByRole('button', { name: t('map.status') })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: t('map.urgency') })).toBeInTheDocument();
      expect(screen.getByText(t('map.truncatedSample'))).toBeInTheDocument();
      expect(screen.getByText(t('map.clusterReports', { count: 4 }))).toBeInTheDocument();
      expect(screen.getByText(t('map.zoomTickets'))).toBeInTheDocument();
    }

    expect(screen.getByTestId('tile-layer')).toHaveAttribute(
      'data-url',
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    );
  });
});

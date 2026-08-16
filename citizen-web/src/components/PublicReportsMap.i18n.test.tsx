import { act, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { PublicReportsMap } from '@/components/PublicReportsMap';
import { setLocale, t, type AppLocale } from '@/i18n';
import { LocaleProvider } from '@/i18n/LocaleProvider';
import type { PublicTicketMapViewportResponse } from '@/types/ticket';

vi.mock('leaflet', () => ({
  default: {
    divIcon: () => ({}),
  },
}));

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children?: ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => null,
  Marker: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Popup: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  useMap: () => ({
    setView: () => undefined,
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

const clusteredViewport: PublicTicketMapViewportResponse = {
  markers: [],
  clusters: [{ id: 'c1', latitude: 33.9, longitude: 35.482, count: 3 }],
  limit: 200,
  truncated: false,
  zoom: 12,
};

describe('PublicReportsMap localization', () => {
  it('localizes cluster popups in en, ar, and fr', async () => {
    render(
      <LocaleProvider>
        <MemoryRouter>
          <PublicReportsMap data={clusteredViewport} onViewportChange={() => undefined} />
        </MemoryRouter>
      </LocaleProvider>,
    );

    for (const locale of LOCALES) {
      await act(async () => {
        setLocale(locale);
      });
      expect(screen.getByText(t('public.clusterNearby', { count: 3 }))).toBeInTheDocument();
      expect(screen.getByText(t('public.zoomReports'))).toBeInTheDocument();
    }
  });
});

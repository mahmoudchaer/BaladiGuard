import { describe, expect, it } from 'vitest';

import type { PublicTicketResponse } from '@/types/ticket';
import {
  cellSizeForRegion,
  clusterPublicReports,
  filterPublicReports,
  isValidMapCoordinate,
  partitionPlottableReports,
  regionForReports,
  uniquePublicCategories,
  type PlottablePublicReport,
} from '@/utils/publicMapClustering';

function makeReport(
  overrides: Partial<PublicTicketResponse> & {
    ticketNumber: string;
    latitude?: number;
    longitude?: number;
  },
): PublicTicketResponse {
  const { latitude = 33.89, longitude = 35.48, ticketNumber, ...rest } = overrides;
  return {
    ticketNumber,
    status: rest.status ?? 'IN_PROGRESS',
    category: rest.category ?? 'road_damage',
    description: rest.description ?? 'Synthetic public report for clustering tests.',
    location: rest.location ?? { addressText: 'Hamra, Beirut' },
    mapLocation: {
      addressText: 'Hamra, Beirut',
      latitude,
      longitude,
    },
    department: { name: 'Road Maintenance' },
    attribution: { displayName: 'Community member', isNamed: false },
    photoUrl: null,
    createdAt: '2026-08-01T00:00:00Z',
    updatedAt: '2026-08-01T00:00:00Z',
    ...rest,
  };
}

describe('isValidMapCoordinate', () => {
  it('accepts finite in-range coordinates', () => {
    expect(isValidMapCoordinate(33.89, 35.48)).toBe(true);
  });

  it('rejects invalid or out-of-range coordinates', () => {
    expect(isValidMapCoordinate(Number.NaN, 35)).toBe(false);
    expect(isValidMapCoordinate(33, Number.POSITIVE_INFINITY)).toBe(false);
    expect(isValidMapCoordinate(120, 35)).toBe(false);
    expect(isValidMapCoordinate(33, 200)).toBe(false);
    expect(isValidMapCoordinate('33' as unknown as number, 35)).toBe(false);
  });
});

describe('partitionPlottableReports', () => {
  it('keeps valid points and counts invalid ones', () => {
    const good = makeReport({ ticketNumber: 'BG-1', latitude: 33.9, longitude: 35.5 });
    const bad = makeReport({
      ticketNumber: 'BG-2',
      latitude: Number.NaN,
      longitude: 35.5,
    });
    const result = partitionPlottableReports([good, bad]);
    expect(result.skippedCount).toBe(1);
    expect(result.plottable).toHaveLength(1);
    expect(result.plottable[0].ticketNumber).toBe('BG-1');
  });
});

describe('filterPublicReports', () => {
  const items = [
    makeReport({ ticketNumber: 'BG-1', status: 'IN_PROGRESS', category: 'road_damage' }),
    makeReport({ ticketNumber: 'BG-2', status: 'RESOLVED', category: 'waste' }),
    makeReport({ ticketNumber: 'BG-3', status: 'IN_PROGRESS', category: 'waste' }),
  ];

  it('filters by status and category', () => {
    expect(
      filterPublicReports(items, { status: 'IN_PROGRESS', category: 'ALL' }).map(
        (item) => item.ticketNumber,
      ),
    ).toEqual(['BG-1', 'BG-3']);
    expect(
      filterPublicReports(items, { status: 'ALL', category: 'waste' }).map(
        (item) => item.ticketNumber,
      ),
    ).toEqual(['BG-2', 'BG-3']);
    expect(
      filterPublicReports(items, {
        status: 'IN_PROGRESS',
        category: 'waste',
      }).map((item) => item.ticketNumber),
    ).toEqual(['BG-3']);
  });
});

describe('clusterPublicReports', () => {
  function toPlottable(reports: PublicTicketResponse[]): PlottablePublicReport[] {
    return partitionPlottableReports(reports).plottable;
  }

  it('clusters nearby markers when zoomed out', () => {
    const reports = Array.from({ length: 8 }, (_, index) =>
      makeReport({
        ticketNumber: `BG-${index}`,
        latitude: 33.89 + index * 0.00005,
        longitude: 35.48 + index * 0.00005,
      }),
    );
    const features = clusterPublicReports(toPlottable(reports), {
      latitude: 33.89,
      longitude: 35.48,
      latitudeDelta: 0.08,
      longitudeDelta: 0.08,
    });
    const clusters = features.filter((feature) => feature.kind === 'cluster');
    expect(clusters.length).toBeGreaterThan(0);
    const total = features.reduce(
      (sum, feature) => sum + (feature.kind === 'cluster' ? feature.count : 1),
      0,
    );
    expect(total).toBe(8);
    expect(clusters[0].count).toBeGreaterThan(1);
  });

  it('expands into single markers when zoomed in', () => {
    const reports = [
      makeReport({ ticketNumber: 'BG-A', latitude: 33.89, longitude: 35.48 }),
      makeReport({ ticketNumber: 'BG-B', latitude: 33.891, longitude: 35.481 }),
    ];
    const features = clusterPublicReports(toPlottable(reports), {
      latitude: 33.89,
      longitude: 35.48,
      latitudeDelta: 0.002,
      longitudeDelta: 0.002,
    });
    expect(features.every((feature) => feature.kind === 'single')).toBe(true);
    expect(features).toHaveLength(2);
  });

  it('uses only provided points for cluster counts', () => {
    const dense = Array.from({ length: 12 }, (_, index) =>
      makeReport({
        ticketNumber: `BG-D-${index}`,
        latitude: 33.9,
        longitude: 35.5 + index * 0.00001,
      }),
    );
    const features = clusterPublicReports(toPlottable(dense), {
      latitude: 33.9,
      longitude: 35.5,
      latitudeDelta: 0.05,
      longitudeDelta: 0.05,
    });
    const countSum = features.reduce(
      (sum, feature) => sum + (feature.kind === 'cluster' ? feature.count : 1),
      0,
    );
    expect(countSum).toBe(12);
  });
});

describe('regionForReports / cellSizeForRegion', () => {
  it('builds a padded region and shrinks cell size as the map zooms in', () => {
    const region = regionForReports(
      [
        { latitude: 33.89, longitude: 35.48 },
        { latitude: 33.9, longitude: 35.49 },
      ],
      1.5,
    );
    expect(region.latitude).toBeCloseTo(33.895, 3);
    expect(region.latitudeDelta).toBeGreaterThan(0.01);

    const zoomedOut = cellSizeForRegion({
      latitude: 33.9,
      longitude: 35.5,
      latitudeDelta: 0.1,
      longitudeDelta: 0.1,
    });
    const zoomedIn = cellSizeForRegion({
      latitude: 33.9,
      longitude: 35.5,
      latitudeDelta: 0.01,
      longitudeDelta: 0.01,
    });
    expect(zoomedIn).toBeLessThan(zoomedOut);
  });
});

describe('uniquePublicCategories', () => {
  it('returns sorted unique non-pending categories', () => {
    const items = [
      makeReport({ ticketNumber: '1', category: 'waste' }),
      makeReport({ ticketNumber: '2', category: 'road_damage' }),
      makeReport({ ticketNumber: '3', category: 'waste' }),
      makeReport({ ticketNumber: '4', category: 'PENDING_CLASSIFICATION' }),
    ];
    expect(uniquePublicCategories(items)).toEqual(['road_damage', 'waste']);
  });
});

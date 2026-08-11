import type { PublicTicketResponse, TicketStatus } from '@/types/ticket';

export type PublicMapRegion = {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
};

export type PlottablePublicReport = {
  ticketNumber: string;
  latitude: number;
  longitude: number;
  report: PublicTicketResponse;
};

export type PublicMapSingle = {
  kind: 'single';
  id: string;
  latitude: number;
  longitude: number;
  report: PublicTicketResponse;
};

export type PublicMapClusterGroup = {
  kind: 'cluster';
  id: string;
  latitude: number;
  longitude: number;
  count: number;
  reports: PublicTicketResponse[];
};

export type PublicMapFeature = PublicMapSingle | PublicMapClusterGroup;

export type PublicBrowseFilters = {
  status: TicketStatus | 'ALL';
  category: string | 'ALL';
};

/** Beirut-ish default viewport for empty/non-plottable sets. */
export const DEFAULT_PUBLIC_MAP_REGION: PublicMapRegion = {
  latitude: 33.8938,
  longitude: 35.5018,
  latitudeDelta: 0.06,
  longitudeDelta: 0.06,
};

const MAX_LAT = 90;
const MAX_LNG = 180;

/**
 * Strict coordinate check for public map pins.
 * Skips non-finite / out-of-range values so maps never crash.
 */
export function isValidMapCoordinate(latitude: unknown, longitude: unknown): boolean {
  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return false;
  }
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return false;
  }
  if (latitude < -MAX_LAT || latitude > MAX_LAT) {
    return false;
  }
  if (longitude < -MAX_LNG || longitude > MAX_LNG) {
    return false;
  }
  return true;
}

export function partitionPlottableReports(items: PublicTicketResponse[]): {
  plottable: PlottablePublicReport[];
  skippedCount: number;
} {
  const plottable: PlottablePublicReport[] = [];
  let skippedCount = 0;

  for (const report of items) {
    const latitude = report.mapLocation?.latitude;
    const longitude = report.mapLocation?.longitude;
    if (!isValidMapCoordinate(latitude, longitude)) {
      skippedCount += 1;
      continue;
    }
    plottable.push({
      ticketNumber: report.ticketNumber,
      latitude,
      longitude,
      report,
    });
  }

  return { plottable, skippedCount };
}

export function filterPublicReports(
  items: PublicTicketResponse[],
  filters: PublicBrowseFilters,
): PublicTicketResponse[] {
  return items.filter((item) => {
    if (filters.status !== 'ALL' && item.status !== filters.status) {
      return false;
    }
    if (filters.category !== 'ALL') {
      const category = (item.category ?? '').toLowerCase();
      if (category !== filters.category.toLowerCase()) {
        return false;
      }
    }
    return true;
  });
}

/**
 * Grid-assisted proximity clustering.
 * Cell size tracks viewport zoom. Nearby points merge when within the cluster
 * distance threshold, including pairs split only by absolute grid cell boundaries.
 */
export function cellSizeForRegion(region: PublicMapRegion): number {
  const span = Math.max(region.latitudeDelta, region.longitudeDelta);
  // Roughly ~6–8 bins across the visible span so counts read as hotspots.
  return Math.max(span / 7, 0.0004);
}

/** Euclidean distance in degree space (enough for local civic map proximity). */
export function distanceDegrees(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const dLat = a.latitude - b.latitude;
  const dLng = a.longitude - b.longitude;
  return Math.hypot(dLat, dLng);
}

/**
 * Merge radius for clustering. Equal to the grid cell size so points in adjacent
 * cells that still fall within one “hotspot” bin are treated as one cluster.
 */
export function clusterDistanceThreshold(region: PublicMapRegion): number {
  return cellSizeForRegion(region);
}

function cellKey(row: number, col: number): string {
  return `${row}:${col}`;
}

export function clusterPublicReports(
  plottable: PlottablePublicReport[],
  region: PublicMapRegion,
): PublicMapFeature[] {
  if (plottable.length === 0) {
    return [];
  }

  const threshold = clusterDistanceThreshold(region);
  const cellSize = threshold;
  const n = plottable.length;

  // Spatial index for candidate pairs (self + 8 neighbors).
  const cells = new Map<string, number[]>();
  for (let index = 0; index < n; index += 1) {
    const point = plottable[index];
    const row = Math.floor(point.latitude / cellSize);
    const col = Math.floor(point.longitude / cellSize);
    const key = cellKey(row, col);
    const bucket = cells.get(key);
    if (bucket) {
      bucket.push(index);
    } else {
      cells.set(key, [index]);
    }
  }

  // Union-find over points within proximity threshold.
  const parent = Array.from({ length: n }, (_, index) => index);
  const rank = new Array<number>(n).fill(0);

  const find = (index: number): number => {
    let current = index;
    while (parent[current] !== current) {
      parent[current] = parent[parent[current]];
      current = parent[current];
    }
    return current;
  };

  const union = (a: number, b: number) => {
    let rootA = find(a);
    let rootB = find(b);
    if (rootA === rootB) {
      return;
    }
    if (rank[rootA] < rank[rootB]) {
      const swap = rootA;
      rootA = rootB;
      rootB = swap;
    }
    parent[rootB] = rootA;
    if (rank[rootA] === rank[rootB]) {
      rank[rootA] += 1;
    }
  };

  for (let index = 0; index < n; index += 1) {
    const point = plottable[index];
    const row = Math.floor(point.latitude / cellSize);
    const col = Math.floor(point.longitude / cellSize);
    for (let dRow = -1; dRow <= 1; dRow += 1) {
      for (let dCol = -1; dCol <= 1; dCol += 1) {
        const neighbors = cells.get(cellKey(row + dRow, col + dCol));
        if (!neighbors) {
          continue;
        }
        for (const other of neighbors) {
          if (other <= index) {
            continue;
          }
          if (distanceDegrees(point, plottable[other]) <= threshold) {
            union(index, other);
          }
        }
      }
    }
  }

  const groups = new Map<number, PlottablePublicReport[]>();
  for (let index = 0; index < n; index += 1) {
    const root = find(index);
    const group = groups.get(root);
    if (group) {
      group.push(plottable[index]);
    } else {
      groups.set(root, [plottable[index]]);
    }
  }

  const features: PublicMapFeature[] = [];
  for (const points of groups.values()) {
    if (points.length === 1) {
      const only = points[0];
      features.push({
        kind: 'single',
        id: `single-${only.ticketNumber}`,
        latitude: only.latitude,
        longitude: only.longitude,
        report: only.report,
      });
      continue;
    }

    let latSum = 0;
    let lngSum = 0;
    const ticketNumbers: string[] = [];
    for (const point of points) {
      latSum += point.latitude;
      lngSum += point.longitude;
      ticketNumbers.push(point.ticketNumber);
    }
    ticketNumbers.sort();
    features.push({
      kind: 'cluster',
      id: `cluster-${ticketNumbers.join('_')}`,
      latitude: latSum / points.length,
      longitude: lngSum / points.length,
      count: points.length,
      reports: points.map((point) => point.report),
    });
  }

  return features;
}

/** Region that frames all reports with padding for “zoom into cluster”. */
export function regionForReports(
  reports: Array<{ latitude: number; longitude: number }>,
  paddingFactor = 1.6,
): PublicMapRegion {
  if (reports.length === 0) {
    return DEFAULT_PUBLIC_MAP_REGION;
  }
  if (reports.length === 1) {
    return {
      latitude: reports[0].latitude,
      longitude: reports[0].longitude,
      latitudeDelta: 0.012,
      longitudeDelta: 0.012,
    };
  }

  let minLat = reports[0].latitude;
  let maxLat = reports[0].latitude;
  let minLng = reports[0].longitude;
  let maxLng = reports[0].longitude;
  for (const report of reports) {
    minLat = Math.min(minLat, report.latitude);
    maxLat = Math.max(maxLat, report.latitude);
    minLng = Math.min(minLng, report.longitude);
    maxLng = Math.max(maxLng, report.longitude);
  }

  const latitude = (minLat + maxLat) / 2;
  const longitude = (minLng + maxLng) / 2;
  const latitudeDelta = Math.max((maxLat - minLat) * paddingFactor, 0.008);
  const longitudeDelta = Math.max((maxLng - minLng) * paddingFactor, 0.008);

  return { latitude, longitude, latitudeDelta, longitudeDelta };
}

/**
 * Whether framing these points and re-clustering at that zoom still yields one
 * multi-report cluster (typical for identical coordinates / same landmark).
 * When this is false, zoom-to-expand is a no-op and callers should offer a report picker.
 */
export function clusterCanExpandByZoom(points: PlottablePublicReport[]): boolean {
  if (points.length <= 1) {
    return false;
  }
  const framed = regionForReports(points, 1.35);
  const features = clusterPublicReports(points, framed);
  if (features.length !== 1) {
    return true;
  }
  const only = features[0];
  return only.kind === 'single' || only.count < points.length;
}

export function initialRegionForPlottable(plottable: PlottablePublicReport[]): PublicMapRegion {
  if (plottable.length === 0) {
    return DEFAULT_PUBLIC_MAP_REGION;
  }
  return regionForReports(plottable, 1.8);
}

/** Distinct categories present in the public response for filter chips. */
export function uniquePublicCategories(items: PublicTicketResponse[]): string[] {
  const seen = new Set<string>();
  for (const item of items) {
    if (item.category && item.category.toLowerCase() !== 'pending_classification') {
      seen.add(item.category.toLowerCase());
    }
  }
  return Array.from(seen).sort();
}

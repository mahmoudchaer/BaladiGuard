import { describe, expect, it } from 'vitest';

import {
  assistantFiltersFromApplied,
  buildMapPath,
  buildTicketDetailPath,
  buildTicketListPath,
  buildWorkforcePath,
  parseDashboardSearchParams,
} from '@/utils/dashboardNavigation';

describe('dashboardNavigation', () => {
  it('serializes only safe structured filters', () => {
    expect(
      buildTicketListPath({
        urgency: 'high,critical',
        openOnly: true,
        ticketIds: ['tkt_1', 'not safe id with space'],
      }),
    ).toBe('/?urgency=high%2Ccritical&openOnly=true&ticketIds=tkt_1');
  });

  it('never copies private-looking values into ticket paths', () => {
    expect(buildTicketDetailPath('tkt_ok')).toBe('/tickets/tkt_ok');
    expect(buildTicketDetailPath('nour@example.com')).toBe('/');
    expect(buildWorkforcePath({ workerId: 'wrk_1' })).toBe('/workforce?workerId=wrk_1');
  });

  it('parses map bounds and ignores unknown keys', () => {
    const params = new URLSearchParams(
      'south=33.8&west=35.4&north=33.9&east=35.5&zoom=16&q=secret+phone&description=nope',
    );
    const parsed = parseDashboardSearchParams(params);
    expect(parsed.south).toBe(33.8);
    expect(parsed.q).toBeUndefined();
    expect(buildMapPath(parsed)).toContain('south=33.8');
    expect(buildMapPath(parsed)).not.toContain('secret');
  });

  it('keeps assistant appliedFilters to documented list keys', () => {
    expect(
      assistantFiltersFromApplied({
        urgency: 'high,critical',
        openOnly: 'true',
        cellSizeDegrees: '0.002',
      }),
    ).toEqual({ urgency: 'high,critical', openOnly: true });
  });
});

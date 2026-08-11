import { describe, expect, it } from 'vitest';

import {
  filterCountryDialingOptions,
  findCountryDialingOption,
  formatCountryDialingLabel,
  getCountryDisplayName,
  listCountryDialingOptions,
} from '@/utils/countryDialing';

describe('countryDialing metadata', () => {
  it('lists countries alphabetically by localized display name', () => {
    const options = listCountryDialingOptions('en');
    expect(options.length).toBeGreaterThan(200);

    const names = options.map((option) => option.name);
    const sorted = [...names].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' }));
    expect(names).toEqual(sorted);
  });

  it('includes Lebanon with ISO region and +961 dialing code', () => {
    const lebanon = findCountryDialingOption('LB');
    expect(lebanon).toMatchObject({
      region: 'LB',
      callingCode: '961',
    });
    expect(lebanon?.label).toBe(formatCountryDialingLabel(lebanon!.name, '961'));
    expect(lebanon?.label).toContain('(+961)');
  });

  it('keeps countries that share a dialing prefix as separate ISO entries', () => {
    const usa = findCountryDialingOption('US');
    const canada = findCountryDialingOption('CA');
    expect(usa?.callingCode).toBe('1');
    expect(canada?.callingCode).toBe('1');
    expect(usa?.region).toBe('US');
    expect(canada?.region).toBe('CA');
    expect(usa?.label).not.toBe(canada?.label);
  });

  it('falls back to English country names when a locale is unavailable', () => {
    const english = getCountryDisplayName('LB', 'en');
    const fallback = getCountryDisplayName('LB', 'zz-unsupported');
    expect(fallback).toBe(english);
    expect(english.toLowerCase()).toContain('lebanon');
  });

  it('filters by country name, ISO code, and dialing code', () => {
    const options = listCountryDialingOptions('en');

    expect(filterCountryDialingOptions(options, 'Leb').some((o) => o.region === 'LB')).toBe(true);
    expect(filterCountryDialingOptions(options, 'lb').some((o) => o.region === 'LB')).toBe(true);
    expect(filterCountryDialingOptions(options, '+961').some((o) => o.region === 'LB')).toBe(true);
    expect(filterCountryDialingOptions(options, '961').some((o) => o.region === 'LB')).toBe(true);

    const plusOne = filterCountryDialingOptions(options, '+1');
    expect(plusOne.some((o) => o.region === 'US')).toBe(true);
    expect(plusOne.some((o) => o.region === 'CA')).toBe(true);
  });
});

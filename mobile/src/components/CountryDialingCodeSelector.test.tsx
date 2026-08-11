import React from 'react';
import { act } from 'react-test-renderer';
import { describe, expect, it } from 'vitest';

import { CountryDialingCodeSelector } from '@/components/CountryDialingCodeSelector';
import { renderWithProviders } from '@/test/render';

/** Prefer host nodes over the composite that forwards testID. */
function findByTestId(screen: ReturnType<typeof renderWithProviders>, testID: string) {
  const hosts = screen.root.findAll(
    (node) =>
      node.props.testID === testID &&
      (typeof node.type === 'string' || typeof node.props.onPress === 'function'),
  );
  if (hosts.length > 0) {
    return hosts[hosts.length - 1]!;
  }
  return screen.root.findByProps({ testID });
}

describe('CountryDialingCodeSelector', () => {
  it('defaults the selected value to Lebanon (+961) for LB', () => {
    const screen = renderWithProviders(
      <CountryDialingCodeSelector value="LB" onChange={() => undefined} />,
    );

    expect(findByTestId(screen, 'country-dialing-selector-value').props.children).toMatch(
      /\(\+961\)/,
    );
    const trigger = findByTestId(screen, 'country-dialing-selector');
    expect(trigger.props.accessibilityLabel).toBe('Country');
    expect(trigger.props.accessibilityValue.text).toMatch(/Lebanon/i);
  });

  it('opens a searchable list and maps selection to the ISO region code', async () => {
    let selected = 'LB';
    const screen = renderWithProviders(
      <CountryDialingCodeSelector
        value={selected}
        onChange={(region) => {
          selected = region;
        }}
      />,
    );

    await act(async () => {
      findByTestId(screen, 'country-dialing-selector').props.onPress();
    });

    expect(findByTestId(screen, 'country-dialing-selector-modal').props.visible).toBe(true);

    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-search').props.onChangeText('france');
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-option-FR').props.onPress();
    });

    expect(selected).toBe('FR');
  });

  it('does not collapse countries that share +1 into a single identity', async () => {
    const screen = renderWithProviders(
      <CountryDialingCodeSelector value="US" onChange={() => undefined} />,
    );

    await act(async () => {
      findByTestId(screen, 'country-dialing-selector').props.onPress();
    });
    await act(async () => {
      findByTestId(screen, 'country-dialing-selector-search').props.onChangeText('+1');
    });

    expect(findByTestId(screen, 'country-dialing-selector-option-US')).toBeTruthy();
    expect(findByTestId(screen, 'country-dialing-selector-option-CA')).toBeTruthy();
  });
});

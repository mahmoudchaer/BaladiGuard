import React from 'react';
import { Image } from 'react-native';
import { act } from 'react-test-renderer';
import { describe, expect, it } from 'vitest';

import { ReportPhoto } from '@/components/ReportPhoto';
import { renderWithProviders } from '@/test/render';

function findByTestId(screen: ReturnType<typeof renderWithProviders>, testID: string) {
  return screen.root.findByProps({ testID });
}

describe('ReportPhoto', () => {
  it('retries loading after a failed URI is replaced with a working URI', async () => {
    const screen = renderWithProviders(
      <ReportPhoto
        uri="https://example.com/bad.jpg"
        accessibilityLabel="Report photo"
        testID="photo"
      />,
    );

    const image = screen.root.findByType(Image);
    expect(image.props.resizeMode).toBe('contain');
    expect(typeof image.props.onError).toBe('function');

    await act(async () => {
      image.props.onError({ nativeEvent: { error: 'failed' } });
    });
    expect(findByTestId(screen, 'photo-fallback')).toBeTruthy();

    await act(async () => {
      screen.update(
        <ReportPhoto
          uri="https://example.com/good.jpg"
          accessibilityLabel="Report photo"
          testID="photo"
        />,
      );
    });

    const recovered = screen.root.findByType(Image);
    expect(recovered.props.source).toEqual({
      uri: 'https://example.com/good.jpg',
    });
  });
});

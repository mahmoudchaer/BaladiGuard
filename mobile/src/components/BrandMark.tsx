import { StyleSheet, View } from 'react-native';

import { colors, radii } from '@/theme';

type BrandMarkProps = {
  size?: number;
  muted?: boolean;
};

/**
 * Geometric cedar brand mark (View-based — no SVG dependency).
 * Brand contexts only: wordmark, auth, selected empty/success.
 */
export function BrandMark({ size = 28, muted = false }: BrandMarkProps) {
  const opacity = muted ? 0.14 : 1;
  const canopy = muted ? colors.brand : colors.brand;
  const trunk = muted ? colors.brandDark : colors.brandDark;
  const unit = size / 32;

  return (
    <View
      style={[styles.root, { width: size, height: size, opacity }]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      <View
        style={[
          styles.tier,
          {
            borderBottomColor: canopy,
            borderLeftWidth: 10 * unit,
            borderRightWidth: 10 * unit,
            borderBottomWidth: 8 * unit,
            top: 2 * unit,
          },
        ]}
      />
      <View
        style={[
          styles.tier,
          {
            borderBottomColor: canopy,
            borderLeftWidth: 12 * unit,
            borderRightWidth: 12 * unit,
            borderBottomWidth: 9 * unit,
            top: 8 * unit,
          },
        ]}
      />
      <View
        style={[
          styles.tier,
          {
            borderBottomColor: canopy,
            borderLeftWidth: 14 * unit,
            borderRightWidth: 14 * unit,
            borderBottomWidth: 10 * unit,
            top: 14 * unit,
          },
        ]}
      />
      <View
        style={[
          styles.trunk,
          {
            backgroundColor: trunk,
            width: 4 * unit,
            height: 8 * unit,
            bottom: 2 * unit,
          },
        ]}
      />
    </View>
  );
}

/** Thin red–white–red accent (Lebanon rhythm; avoids Italy green-white-red). */
export function BrandStripe() {
  return (
    <View style={styles.stripe} accessibilityElementsHidden importantForAccessibility="no">
      <View style={[styles.band, styles.bandRed]} />
      <View style={[styles.band, styles.bandWhite]} />
      <View style={[styles.band, styles.bandRed]} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    alignItems: 'center',
    justifyContent: 'flex-start',
  },
  tier: {
    position: 'absolute',
    width: 0,
    height: 0,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderStyle: 'solid',
  },
  trunk: {
    position: 'absolute',
    borderRadius: 1,
  },
  stripe: {
    flexDirection: 'row',
    height: 3,
    width: 44,
    borderRadius: radii.pill,
    overflow: 'hidden',
    marginBottom: 4,
  },
  band: {
    flex: 1,
  },
  bandRed: {
    backgroundColor: colors.accent,
  },
  bandWhite: {
    backgroundColor: '#F8FAFB',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
});

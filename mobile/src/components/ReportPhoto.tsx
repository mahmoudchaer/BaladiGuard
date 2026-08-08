import { useState } from 'react';
import { Image, StyleSheet, View, type StyleProp, type ImageStyle, type ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, typography } from '@/theme';

type ReportPhotoProps = {
  uri?: string | null;
  accessibilityLabel: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
  imageStyle?: StyleProp<ImageStyle>;
  /** compact = feed thumbnail; hero = detail banner */
  variant?: 'compact' | 'hero';
};

export function ReportPhoto({
  uri,
  accessibilityLabel,
  testID,
  style,
  imageStyle,
  variant = 'compact',
}: ReportPhotoProps) {
  const [failed, setFailed] = useState(false);
  const isHero = variant === 'hero';

  if (!uri || failed) {
    return (
      <View
        style={[styles.fallback, isHero ? styles.fallbackHero : styles.fallbackCompact, style]}
        accessibilityLabel={failed ? 'Photo unavailable' : 'No photo attached'}
        testID={testID ? `${testID}-fallback` : undefined}
      >
        <Text style={styles.fallbackText}>{failed ? 'Photo unavailable' : 'No photo'}</Text>
      </View>
    );
  }

  return (
    <Image
      source={{ uri }}
      style={[isHero ? styles.hero : styles.thumb, imageStyle, style as ImageStyle]}
      resizeMode="cover"
      accessibilityLabel={accessibilityLabel}
      testID={testID}
      onError={() => setFailed(true)}
    />
  );
}

const styles = StyleSheet.create({
  thumb: {
    width: 88,
    height: 88,
    borderRadius: radii.md,
    backgroundColor: colors.surfaceSubtle,
  },
  hero: {
    width: '100%',
    height: 220,
    borderRadius: radii.lg,
    backgroundColor: colors.surfaceSubtle,
  },
  fallback: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSubtle,
  },
  fallbackCompact: {
    width: 88,
    height: 88,
    borderRadius: radii.md,
  },
  fallbackHero: {
    width: '100%',
    height: 160,
    borderRadius: radii.lg,
  },
  fallbackText: {
    color: colors.textMuted,
    fontSize: typography.metadata,
    fontWeight: '600',
    paddingHorizontal: spacing[2],
    textAlign: 'center',
  },
});

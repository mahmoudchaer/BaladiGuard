import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, typography } from '@/theme';

export type ReportWizardStepKey = 'details' | 'photo' | 'location' | 'review';

export const REPORT_WIZARD_STEP_ORDER: ReportWizardStepKey[] = [
  'details',
  'photo',
  'location',
  'review',
];

const STEP_LABELS: Record<ReportWizardStepKey, string> = {
  details: 'Details',
  photo: 'Photo',
  location: 'Location',
  review: 'Review',
};

type StepProgressProps = {
  currentStep: ReportWizardStepKey;
};

/** Plain, dependency-free step indicator (no Material progress bar). */
export function StepProgress({ currentStep }: StepProgressProps) {
  const currentIndex = REPORT_WIZARD_STEP_ORDER.indexOf(currentStep);
  const total = REPORT_WIZARD_STEP_ORDER.length;

  return (
    <View
      style={styles.container}
      accessibilityRole="progressbar"
      accessibilityLabel={`Step ${currentIndex + 1} of ${total}: ${STEP_LABELS[currentStep]}`}
    >
      <View style={styles.track}>
        {REPORT_WIZARD_STEP_ORDER.map((step, index) => {
          const isActive = index <= currentIndex;
          const isLast = index === total - 1;
          return (
            <View key={step} style={styles.segmentWrap}>
              <View style={[styles.dot, isActive && styles.dotActive]} />
              {isLast ? null : (
                <View style={[styles.line, index < currentIndex && styles.lineActive]} />
              )}
            </View>
          );
        })}
      </View>
      <Text variant="labelLarge" style={styles.label}>
        Step {currentIndex + 1} of {total} · {STEP_LABELS[currentStep]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[2],
  },
  track: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  segmentWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: radii.pill,
    borderWidth: 2,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  dotActive: {
    borderColor: colors.brand,
    backgroundColor: colors.brand,
  },
  line: {
    flex: 1,
    height: 2,
    marginHorizontal: 4,
    backgroundColor: colors.border,
  },
  lineActive: {
    backgroundColor: colors.brand,
  },
  label: {
    color: colors.textSecondary,
    fontWeight: '600',
    fontSize: typography.bodyCompact,
  },
});

import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, typography } from '@/theme';

export type ReportWizardStepKey = 'details' | 'photo' | 'location' | 'review';

export const REPORT_WIZARD_STEP_ORDER: ReportWizardStepKey[] = [
  'details',
  'photo',
  'location',
  'review',
];

const STEP_LABEL_KEYS: Record<ReportWizardStepKey, string> = {
  details: 'report.stepNameDetails',
  photo: 'report.stepNamePhoto',
  location: 'report.stepNameLocation',
  review: 'report.stepNameReview',
};

type StepProgressProps = {
  currentStep: ReportWizardStepKey;
};

/** Plain, dependency-free step indicator (no Material progress bar). */
export function StepProgress({ currentStep }: StepProgressProps) {
  const { t } = useI18n();
  const currentIndex = REPORT_WIZARD_STEP_ORDER.indexOf(currentStep);
  const total = REPORT_WIZARD_STEP_ORDER.length;
  const stepLabel = t(STEP_LABEL_KEYS[currentStep]);
  const progressLabel = t('report.stepProgress', {
    current: currentIndex + 1,
    total,
    label: stepLabel,
  });

  return (
    <View
      style={styles.container}
      accessibilityRole="progressbar"
      accessibilityLabel={progressLabel}
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
        {progressLabel}
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

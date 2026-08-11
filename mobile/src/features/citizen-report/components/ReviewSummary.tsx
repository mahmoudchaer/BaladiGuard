import { Image, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import type { Control } from 'react-hook-form';
import { useWatch } from 'react-hook-form';

import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type { ReportWizardStepKey } from '@/features/citizen-report/components/StepProgress';

type ReviewSummaryProps = {
  control: Control<ReportFormValues>;
  onEditStep: (step: ReportWizardStepKey) => void;
};

/** Review is deliberately plain (no Material cards) so it reads like a checklist, not a dashboard. */
export function ReviewSummary({ control, onEditStep }: ReviewSummaryProps) {
  const description = useWatch({ control, name: 'description' });
  const photoUri = useWatch({ control, name: 'photoUri' });
  const addressText = useWatch({ control, name: 'addressText' });

  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.title}>
        Review your report
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        Check everything below before you submit. You can edit any section.
      </Text>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            Description
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('details')}
          >
            Edit
          </Button>
        </View>
        <Text variant="bodyMedium" style={styles.sectionText}>
          {description || 'Not provided yet.'}
        </Text>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            Photo
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('photo')}
          >
            Edit
          </Button>
        </View>
        {photoUri ? (
          <Image source={{ uri: photoUri }} style={styles.photo} />
        ) : (
          <Text variant="bodyMedium" style={styles.sectionText}>
            No photo attached yet.
          </Text>
        )}
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            Location
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('location')}
          >
            Edit
          </Button>
        </View>
        <Text variant="bodyMedium" style={styles.sectionText}>
          {addressText || 'Not set yet.'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[4],
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  helper: {
    color: colors.textMuted,
  },
  section: {
    gap: spacing[1],
    paddingBottom: spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionLabel: {
    color: colors.textSecondary,
    fontWeight: '700',
    fontSize: typography.label,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  editButton: {
    minHeight: touchTargetMin,
    justifyContent: 'center',
  },
  sectionText: {
    color: colors.text,
  },
  photo: {
    width: '100%',
    height: 180,
    borderRadius: radii.lg,
    backgroundColor: colors.surfaceSubtle,
  },
});

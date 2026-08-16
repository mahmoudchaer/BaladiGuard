import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import type { Control } from 'react-hook-form';
import { useWatch } from 'react-hook-form';

import { ReportPhoto } from '@/components/ReportPhoto';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { ReportFormValues } from '@/schemas/reportFormSchema';
import type { ReportWizardStepKey } from '@/features/citizen-report/components/StepProgress';

type ReviewSummaryProps = {
  control: Control<ReportFormValues>;
  onEditStep: (step: ReportWizardStepKey) => void;
  hasUploadedPhoto?: boolean;
};

/** Review is deliberately plain (no Material cards) so it reads like a checklist, not a dashboard. */
export function ReviewSummary({ control, onEditStep, hasUploadedPhoto }: ReviewSummaryProps) {
  const { t } = useI18n();
  const description = useWatch({ control, name: 'description' });
  const photoUri = useWatch({ control, name: 'photoUri' });
  const addressText = useWatch({ control, name: 'addressText' });

  return (
    <View style={styles.container}>
      <Text variant="titleMedium" style={styles.title}>
        {t('report.reviewTitle')}
      </Text>
      <Text variant="bodySmall" style={styles.helper}>
        {t('report.reviewHelper')}
      </Text>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            {t('report.description')}
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('details')}
          >
            {t('common.edit')}
          </Button>
        </View>
        <Text variant="bodyMedium" style={styles.sectionText}>
          {description || t('report.notProvided')}
        </Text>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            {t('report.photo')}
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('photo')}
          >
            {t('common.edit')}
          </Button>
        </View>
        {photoUri ? (
          <ReportPhoto uri={photoUri} accessibilityLabel={t('report.photo')} variant="hero" />
        ) : hasUploadedPhoto ? (
          <View style={styles.uploadedPhoto}>
            <Text variant="bodyMedium" style={styles.uploadedPhotoText}>
              {t('report.photoUploaded')}
            </Text>
          </View>
        ) : (
          <Text variant="bodyMedium" style={styles.sectionText}>
            {t('report.noPhotoYet')}
          </Text>
        )}
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text variant="labelLarge" style={styles.sectionLabel}>
            {t('report.location')}
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.editButton}
            onPress={() => onEditStep('location')}
          >
            {t('common.edit')}
          </Button>
        </View>
        <Text variant="bodyMedium" style={styles.sectionText}>
          {addressText || t('report.notSetYet')}
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
  uploadedPhoto: {
    minHeight: 72,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.lg,
    backgroundColor: colors.brandSoft,
  },
  uploadedPhotoText: {
    color: colors.brandDark,
    fontWeight: '600',
  },
});

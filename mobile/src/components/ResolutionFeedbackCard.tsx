import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';

import { useI18n } from '@/i18n/LocaleProvider';
import type { CitizenResolutionFeedback, ResolutionFeedbackStatus } from '@/types/ticket';
import { colors, radii, spacing, touchTargetMin } from '@/theme';

type ResolutionFeedbackCardProps = {
  trackingCode: string;
  feedback: CitizenResolutionFeedback;
  submitting?: boolean;
  errorMessage?: string | null;
  onSubmit: (status: ResolutionFeedbackStatus, note?: string) => void;
};

export function ResolutionFeedbackCard({
  trackingCode,
  feedback,
  submitting = false,
  errorMessage,
  onSubmit,
}: ResolutionFeedbackCardProps) {
  const { t } = useI18n();
  const [note, setNote] = useState('');

  if (!feedback.canSubmit && !feedback.status) {
    return null;
  }

  return (
    <View style={styles.card} testID={`resolution-feedback-${trackingCode}`}>
      <Text variant="titleSmall" style={styles.title}>
        {t('feedback.title')}
      </Text>
      {feedback.status ? (
        <Text style={styles.body} testID={`resolution-feedback-submitted-${trackingCode}`}>
          {feedback.status === 'CONFIRMED_FIXED'
            ? t('feedback.confirmed')
            : t('feedback.unresolved')}
        </Text>
      ) : (
        <Text style={styles.body}>{t('feedback.prompt')}</Text>
      )}
      {feedback.canSubmit || feedback.status ? (
        <TextInput
          mode="outlined"
          label={t('feedback.note')}
          value={note}
          onChangeText={setNote}
          maxLength={500}
          multiline
          disabled={submitting}
          testID={`resolution-feedback-note-${trackingCode}`}
        />
      ) : null}
      <View style={styles.actions}>
        <Button
          mode="contained"
          onPress={() => onSubmit('CONFIRMED_FIXED', note.trim() || undefined)}
          loading={submitting}
          disabled={submitting}
          testID={`resolution-feedback-fixed-${trackingCode}`}
        >
          {t('feedback.confirmedFixed')}
        </Button>
        <Button
          mode="outlined"
          onPress={() => onSubmit('STILL_UNRESOLVED', note.trim() || undefined)}
          disabled={submitting}
          testID={`resolution-feedback-unresolved-${trackingCode}`}
        >
          {t('feedback.stillUnresolved')}
        </Button>
      </View>
      {errorMessage ? (
        <HelperText type="error" visible testID={`resolution-feedback-error-${trackingCode}`}>
          {errorMessage}
        </HelperText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: spacing[2],
    padding: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  body: {
    color: colors.textSecondary,
  },
  actions: {
    gap: spacing[2],
    minHeight: touchTargetMin,
  },
});

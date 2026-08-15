import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';

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
  const [note, setNote] = useState('');

  if (!feedback.canSubmit && !feedback.status) {
    return null;
  }

  return (
    <View style={styles.card} testID={`resolution-feedback-${trackingCode}`}>
      <Text variant="titleSmall" style={styles.title}>
        Was this issue fixed?
      </Text>
      {feedback.status ? (
        <Text style={styles.body} testID={`resolution-feedback-submitted-${trackingCode}`}>
          {feedback.status === 'CONFIRMED_FIXED'
            ? 'You confirmed this report was fixed.'
            : 'You told the municipality this is still unresolved.'}
        </Text>
      ) : (
        <Text style={styles.body}>
          Tell the municipality whether the reported issue is actually fixed. Your optional note
          stays private.
        </Text>
      )}
      {feedback.canSubmit || feedback.status ? (
        <TextInput
          mode="outlined"
          label="Private note (optional)"
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
          Confirmed fixed
        </Button>
        <Button
          mode="outlined"
          onPress={() => onSubmit('STILL_UNRESOLVED', note.trim() || undefined)}
          disabled={submitting}
          testID={`resolution-feedback-unresolved-${trackingCode}`}
        >
          Still unresolved
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

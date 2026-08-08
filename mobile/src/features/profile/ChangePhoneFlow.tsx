import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';

import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import { PhoneEntryForm, type PhoneEntrySuccess } from '@/features/citizen-auth/PhoneEntryForm';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import type { CitizenOtpVerifyResponse } from '@/types/citizen';

type ChangePhoneFlowProps = {
  currentPhone: string;
  onVerified: (response: CitizenOtpVerifyResponse) => Promise<void>;
  onCancel: () => void;
};

export function ChangePhoneFlow({ currentPhone, onVerified, onCancel }: ChangePhoneFlowProps) {
  const [challenge, setChallenge] = useState<PhoneEntrySuccess | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleVerified = async (response: CitizenOtpVerifyResponse) => {
    setBusy(true);
    try {
      await onVerified(response);
      setSuccessMessage(`Phone updated to ${response.phone}. Your session was refreshed.`);
      setChallenge(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container} testID="change-phone-flow">
      <Text variant="titleLarge" style={styles.title}>
        Change phone number
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        Your current verified phone is {currentPhone}. Enter a new number and verify it with a
        one-time code. If that number already belongs to another citizen, the change will be
        rejected.
      </Text>

      {successMessage ? (
        <Banner visible icon="check-circle" style={styles.banner} testID="phone-change-success">
          {successMessage}
        </Banner>
      ) : null}

      {challenge ? (
        <OtpVerifyForm
          challengeId={challenge.challengeId}
          expiresIn={challenge.expiresIn}
          phone={challenge.phone}
          region={challenge.region}
          purpose="CHANGE_PHONE"
          onChallengeReplaced={(next) =>
            setChallenge((prev) =>
              prev
                ? {
                    ...prev,
                    challengeId: next.challengeId,
                    expiresIn: next.expiresIn,
                  }
                : prev,
            )
          }
          onVerified={(response) => {
            void handleVerified(response);
          }}
        />
      ) : (
        <PhoneEntryForm
          purpose="CHANGE_PHONE"
          title="New phone number"
          subtitle="We will send a verification code to the new number. Codes and session tokens are never shown here."
          submitLabel="Send verification code"
          onSuccess={setChallenge}
        />
      )}

      <Button
        mode="text"
        onPress={onCancel}
        disabled={busy}
        style={styles.button}
        contentStyle={styles.controlContent}
        textColor={colors.textSecondary}
        testID="cancel-phone-change-button"
      >
        {successMessage ? 'Back to profile' : 'Cancel'}
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[3],
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    color: colors.textSecondary,
    marginBottom: spacing[1],
    lineHeight: 21,
  },
  banner: {
    marginBottom: spacing[1],
    borderRadius: radii.md,
  },
  button: {
    width: '100%',
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
});

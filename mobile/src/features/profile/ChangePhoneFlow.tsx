import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';

import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import { PhoneEntryForm, type PhoneEntrySuccess } from '@/features/citizen-auth/PhoneEntryForm';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin } from '@/theme';
import type { CitizenOtpVerifyResponse } from '@/types/citizen';

type ChangePhoneFlowProps = {
  currentPhone: string;
  onVerified: (response: CitizenOtpVerifyResponse) => Promise<void>;
  onCancel: () => void;
};

export function ChangePhoneFlow({ currentPhone, onVerified, onCancel }: ChangePhoneFlowProps) {
  const { t } = useI18n();
  const [challenge, setChallenge] = useState<PhoneEntrySuccess | null>(null);
  const [updatedPhone, setUpdatedPhone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleVerified = async (response: CitizenOtpVerifyResponse) => {
    setBusy(true);
    try {
      await onVerified(response);
      setUpdatedPhone(response.phone);
      setChallenge(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container} testID="change-phone-flow">
      <Text variant="titleLarge" style={styles.title} accessibilityLabel={t('profile.changePhone')}>
        {t('profile.changePhone')}
      </Text>
      <Text variant="bodyMedium" style={styles.subtitle}>
        {t('profile.changePhoneBody', { phone: currentPhone })}
      </Text>

      {updatedPhone ? (
        <Banner visible icon="check-circle" style={styles.banner} testID="phone-change-success">
          {t('profile.phoneChangeSuccess', { phone: updatedPhone })}
        </Banner>
      ) : null}

      {challenge ? (
        <OtpVerifyForm
          challengeId={challenge.challengeId}
          expiresIn={challenge.expiresIn}
          phone={challenge.phone}
          region={challenge.region}
          purpose="CHANGE_PHONE"
          deliveryChannel={challenge.deliveryChannel}
          onChallengeReplaced={(next) =>
            setChallenge((prev) =>
              prev
                ? {
                    ...prev,
                    challengeId: next.challengeId,
                    expiresIn: next.expiresIn,
                    deliveryChannel: next.deliveryChannel ?? prev.deliveryChannel,
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
          title={t('profile.newPhone')}
          subtitle={t('profile.newPhoneHint')}
          submitLabel={t('profile.sendVerification')}
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
        {updatedPhone ? t('profile.backToProfile') : t('common.cancel')}
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

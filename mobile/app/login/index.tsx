import { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Redirect, useLocalSearchParams, useRouter, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { sanitizeReturnTo } from '@/auth/returnTo';
import { BrandMark, BrandStripe } from '@/components/BrandMark';
import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import { PhoneEntryForm, type PhoneEntrySuccess } from '@/features/citizen-auth/PhoneEntryForm';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, spacing } from '@/theme';
import type { CitizenOtpVerifyResponse } from '@/types/citizen';

type ChallengeState = PhoneEntrySuccess | null;

export default function LoginScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ returnTo?: string | string[] }>();
  const returnTo = useMemo(() => sanitizeReturnTo(params.returnTo), [params.returnTo]);
  const { t } = useI18n();
  const { applyVerifyResponse, contributionReady, isAuthenticated, isLoading } = useCitizenAuth();

  const [challenge, setChallenge] = useState<ChallengeState>(null);

  const finishAndReturn = () => {
    router.replace(returnTo as Href);
  };

  const handleVerified = async (response: CitizenOtpVerifyResponse) => {
    await applyVerifyResponse(response);
    // Verified phone alone is contribution-ready (#270); no mandatory name step.
    finishAndReturn();
  };

  if (!isLoading && isAuthenticated && contributionReady && !challenge) {
    return <Redirect href={returnTo as Href} />;
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.container}>
          <View style={styles.brandBlock}>
            <BrandStripe />
            <BrandMark size={32} />
          </View>
          {challenge ? (
            <OtpVerifyForm
              challengeId={challenge.challengeId}
              expiresIn={challenge.expiresIn}
              phone={challenge.phone}
              region={challenge.region}
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
              onVerified={handleVerified}
            />
          ) : (
            <PhoneEntryForm
              onSuccess={setChallenge}
              title={t('auth.continueTitle')}
              subtitle={t('auth.continueSubtitle')}
            />
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    flexGrow: 1,
  },
  container: {
    flex: 1,
    padding: spacing[5],
  },
  brandBlock: {
    alignItems: 'center',
    gap: spacing[2],
    marginBottom: spacing[5],
  },
});

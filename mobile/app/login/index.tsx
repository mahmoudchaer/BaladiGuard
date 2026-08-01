import { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Redirect, useLocalSearchParams, useRouter, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { sanitizeReturnTo } from '@/auth/returnTo';
import { FullNameForm } from '@/features/citizen-auth/FullNameForm';
import { OtpVerifyForm } from '@/features/citizen-auth/OtpVerifyForm';
import { PhoneEntryForm, type PhoneEntrySuccess } from '@/features/citizen-auth/PhoneEntryForm';
import type { CitizenOtpVerifyResponse } from '@/types/citizen';

type ChallengeState = PhoneEntrySuccess | null;

export default function LoginScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ returnTo?: string | string[] }>();
  const returnTo = useMemo(() => sanitizeReturnTo(params.returnTo), [params.returnTo]);
  const { applyVerifyResponse, completeFullName, contributionReady, isAuthenticated, isLoading } =
    useCitizenAuth();

  const [challenge, setChallenge] = useState<ChallengeState>(null);
  const [needsFullName, setNeedsFullName] = useState(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated && !contributionReady && !challenge) {
      setNeedsFullName(true);
    }
  }, [isLoading, isAuthenticated, contributionReady, challenge]);

  const finishAndReturn = () => {
    router.replace(returnTo as Href);
  };

  const handleVerified = async (response: CitizenOtpVerifyResponse) => {
    await applyVerifyResponse(response);
    if (response.contributionReady) {
      finishAndReturn();
      return;
    }
    setNeedsFullName(true);
  };

  const handleFullName = async (fullName: string) => {
    await completeFullName(fullName);
    finishAndReturn();
  };

  if (!isLoading && isAuthenticated && contributionReady && !challenge && !needsFullName) {
    return <Redirect href={returnTo as Href} />;
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.container}>
          {needsFullName ? (
            <FullNameForm onSubmitName={handleFullName} />
          ) : challenge ? (
            <OtpVerifyForm
              challengeId={challenge.challengeId}
              expiresIn={challenge.expiresIn}
              phone={challenge.phone}
              region={challenge.region}
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
              onVerified={handleVerified}
            />
          ) : (
            <PhoneEntryForm onSuccess={setChallenge} />
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  scroll: {
    flexGrow: 1,
  },
  container: {
    flex: 1,
    padding: 24,
  },
});

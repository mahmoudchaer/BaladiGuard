import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { ChangePhoneFlow } from '@/features/profile/ChangePhoneFlow';
import { ProfileEditForm } from '@/features/profile/ProfileEditForm';
import { ProfileSummary } from '@/features/profile/ProfileSummary';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  CitizenAuthApiError,
  OTP_NETWORK_MESSAGE,
  PROFILE_UPDATE_SUCCESS_MESSAGE,
} from '@/services/api/citizenAuth';
import { draftHasRestorableContent, loadReportDraft } from '@/services/reportDraft';
import { colors, radii, spacing } from '@/theme';
import type { CitizenOtpVerifyResponse, CitizenProfileUpdatePayload } from '@/types/citizen';

type ProfileMode = 'view' | 'edit' | 'changePhone';

export default function ProfileScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const {
    applyVerifyResponse,
    isAuthenticated,
    isLoading,
    logout,
    profile,
    refreshProfile,
    updateProfile,
  } = useCitizenAuth();

  const [mode, setMode] = useState<ProfileMode>('view');
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadErrorKey, setLoadErrorKey] = useState<'unableLoad' | 'unableRefresh' | null>(null);
  const [loadErrorMessage, setLoadErrorMessage] = useState<string | null>(null);
  const [isOfflineCached, setIsOfflineCached] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const didInitialRefresh = useRef(false);

  const reload = useCallback(async () => {
    setIsRefreshing(true);
    setLoadErrorKey(null);
    setLoadErrorMessage(null);
    setIsOfflineCached(false);
    try {
      const next = await refreshProfile();
      if (!next) {
        setLoadErrorKey('unableLoad');
      }
    } catch (error) {
      if (error instanceof CitizenAuthApiError && error.code === 'NETWORK_ERROR') {
        setIsOfflineCached(true);
        setLoadErrorMessage(OTP_NETWORK_MESSAGE);
      } else if (error instanceof CitizenAuthApiError) {
        setLoadErrorMessage(error.message);
      } else {
        setLoadErrorKey('unableRefresh');
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshProfile]);

  useEffect(() => {
    if (!isAuthenticated || isLoading || didInitialRefresh.current) {
      return;
    }
    didInitialRefresh.current = true;
    void reload();
  }, [isAuthenticated, isLoading, reload]);

  const finishLogout = async (retainReportDraft: boolean) => {
    setIsLoggingOut(true);
    try {
      await logout({ retainReportDraft });
      router.replace('/' as Href);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleLogout = () => {
    void (async () => {
      const draft = profile?.userId ? await loadReportDraft(profile.userId) : null;
      if (!draft || !draftHasRestorableContent(draft)) {
        await finishLogout(false);
        return;
      }
      Alert.alert(t('more.signOutTitle'), t('more.signOutBody'), [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('more.keepDraft'),
          onPress: () => {
            void finishLogout(true);
          },
        },
        {
          text: t('more.clearDraft'),
          style: 'destructive',
          onPress: () => {
            void finishLogout(false);
          },
        },
      ]);
    })();
  };

  const handleSave = async (patch: CitizenProfileUpdatePayload) => {
    const next = await updateProfile(patch);
    setSuccessMessage(PROFILE_UPDATE_SUCCESS_MESSAGE);
    setMode('view');
    return next;
  };

  const handlePhoneVerified = async (response: CitizenOtpVerifyResponse) => {
    await applyVerifyResponse(response);
    setSuccessMessage(t('profile.phoneUpdated', { phone: response.phone }));
    setMode('view');
  };

  const loadError =
    loadErrorMessage ??
    (loadErrorKey === 'unableLoad'
      ? t('profile.unableLoad')
      : loadErrorKey === 'unableRefresh'
        ? t('profile.unableRefresh')
        : null);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
        <View style={styles.centered} testID="profile-loading">
          <ActivityIndicator color={colors.brand} />
          <Text variant="bodyMedium" style={styles.muted}>
            {t('profile.loading')}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href={buildLoginHref('/profile') as Href} />;
  }

  if (!profile) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
        <View style={styles.container} testID="profile-empty">
          <Banner visible icon="account-alert" style={styles.banner}>
            {t('profile.empty')}
          </Banner>
          <Button
            mode="contained"
            onPress={() => void reload()}
            buttonColor={colors.brand}
            textColor={colors.textInverse}
            testID="retry-profile-button"
          >
            {t('common.retry')}
          </Button>
          <Button
            mode="text"
            onPress={() => void handleLogout()}
            textColor={colors.textSecondary}
            testID="profile-logout-button"
          >
            {t('common.signOut')}
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.container}>
          {successMessage ? (
            <Banner
              visible
              icon="check-circle"
              style={styles.banner}
              testID="profile-screen-success"
            >
              {successMessage}
            </Banner>
          ) : null}

          {loadError ? (
            <Banner visible icon="alert-circle" style={styles.banner} testID="profile-load-error">
              {isOfflineCached
                ? `${loadError} ${t('profile.offlineSuffix')}`
                : loadError}
            </Banner>
          ) : null}

          {isRefreshing ? (
            <View style={styles.refreshRow} testID="profile-refreshing">
              <ActivityIndicator color={colors.brand} />
              <Text variant="bodySmall" style={styles.muted}>
                {t('profile.refreshing')}
              </Text>
            </View>
          ) : null}

          {mode === 'edit' ? (
            <ProfileEditForm
              profile={profile}
              onSave={handleSave}
              onCancel={() => setMode('view')}
            />
          ) : mode === 'changePhone' ? (
            <ChangePhoneFlow
              currentPhone={profile.phone}
              onVerified={handlePhoneVerified}
              onCancel={() => setMode('view')}
            />
          ) : (
            <ProfileSummary
              profile={profile}
              onEdit={() => {
                setSuccessMessage(null);
                setMode('edit');
              }}
              onChangePhone={() => {
                setSuccessMessage(null);
                setMode('changePhone');
              }}
              onLogout={() => void handleLogout()}
              isLoggingOut={isLoggingOut}
            />
          )}

          {mode === 'view' ? (
            <Button
              mode="text"
              onPress={() => void reload()}
              disabled={isRefreshing}
              textColor={colors.brandDark}
              testID="refresh-profile-button"
            >
              {t('profile.refresh')}
            </Button>
          ) : null}
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
    gap: spacing[3],
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[3],
    padding: spacing[5],
  },
  muted: {
    color: colors.textMuted,
  },
  banner: {
    marginBottom: spacing[1],
    borderRadius: radii.md,
  },
  refreshRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
  },
});

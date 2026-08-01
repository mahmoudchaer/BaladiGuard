import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { ChangePhoneFlow } from '@/features/profile/ChangePhoneFlow';
import { ProfileEditForm } from '@/features/profile/ProfileEditForm';
import { ProfileSummary } from '@/features/profile/ProfileSummary';
import {
  CitizenAuthApiError,
  OTP_NETWORK_MESSAGE,
  PROFILE_UPDATE_SUCCESS_MESSAGE,
} from '@/services/api/citizenAuth';
import type { CitizenOtpVerifyResponse, CitizenProfileUpdatePayload } from '@/types/citizen';

type ProfileMode = 'view' | 'edit' | 'changePhone';

export default function ProfileScreen() {
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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isOfflineCached, setIsOfflineCached] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const didInitialRefresh = useRef(false);

  const reload = useCallback(async () => {
    setIsRefreshing(true);
    setLoadError(null);
    setIsOfflineCached(false);
    try {
      const next = await refreshProfile();
      if (!next) {
        setLoadError('Unable to load your profile. Please sign in again.');
      }
    } catch (error) {
      if (error instanceof CitizenAuthApiError && error.code === 'NETWORK_ERROR') {
        setIsOfflineCached(true);
        setLoadError(OTP_NETWORK_MESSAGE);
      } else if (error instanceof CitizenAuthApiError) {
        setLoadError(error.message);
      } else {
        setLoadError('Unable to refresh your profile right now.');
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

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
      router.replace('/' as Href);
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleSave = async (patch: CitizenProfileUpdatePayload) => {
    const next = await updateProfile(patch);
    setSuccessMessage(PROFILE_UPDATE_SUCCESS_MESSAGE);
    setMode('view');
    return next;
  };

  const handlePhoneVerified = async (response: CitizenOtpVerifyResponse) => {
    await applyVerifyResponse(response);
    setSuccessMessage(`Phone updated to ${response.phone}.`);
    setMode('view');
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
        <View style={styles.centered} testID="profile-loading">
          <ActivityIndicator />
          <Text variant="bodyMedium" style={styles.muted}>
            Loading profile…
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
          <Banner visible icon="account-alert">
            No profile is available for this session.
          </Banner>
          <Button mode="contained" onPress={() => void reload()} testID="retry-profile-button">
            Retry
          </Button>
          <Button mode="text" onPress={() => void handleLogout()} testID="profile-logout-button">
            Sign out
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
                ? `${loadError} Showing the last saved profile on this device.`
                : loadError}
            </Banner>
          ) : null}

          {isRefreshing ? (
            <View style={styles.refreshRow} testID="profile-refreshing">
              <ActivityIndicator />
              <Text variant="bodySmall" style={styles.muted}>
                Refreshing…
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
              testID="refresh-profile-button"
            >
              Refresh profile
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
    backgroundColor: '#FFFFFF',
  },
  scroll: {
    flexGrow: 1,
  },
  container: {
    flex: 1,
    padding: 24,
    gap: 12,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: 24,
  },
  muted: {
    color: '#64748B',
  },
  banner: {
    marginBottom: 4,
  },
  refreshRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
});

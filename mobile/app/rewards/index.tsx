import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { useI18n } from '@/i18n/LocaleProvider';
import { getMyRewards, type CitizenRewards } from '@/services/api/rewards';
import { colors, spacing } from '@/theme';

export default function RewardsScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useCitizenAuth();
  const [data, setData] = useState<CitizenRewards | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getMyRewards());
    } catch (err) {
      setError(err instanceof Error ? err.message : t('rewards.loadFailed'));
    }
  }, [t]);

  useEffect(() => {
    if (isAuthenticated) void load();
  }, [isAuthenticated, load]);

  if (isLoading) return null;
  if (!isAuthenticated) return <Redirect href={buildLoginHref('/rewards') as Href} />;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>{t('rewards.title')}</Text>
        <Text style={styles.lede}>{t('rewards.lede')}</Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {data ? (
          <View style={styles.card}>
            <Text>
              {t('rewards.confirmed')}: {data.confirmedPoints}
            </Text>
            <Text>
              {t('rewards.pending')}: {data.pendingPoints}
            </Text>
            <Text>
              {t('rewards.monthly')}: {data.monthlyPoints}
            </Text>
            <Text>
              {t('rewards.level')}: {data.levelTitle}
            </Text>
            <Text>
              {t('rewards.rank')}: {data.privateRankAllTime ?? '—'}
            </Text>
            {!data.participation.eligible ? (
              <Text style={styles.hint}>{t('rewards.completeProfile')}</Text>
            ) : null}
            {data.confirmedPoints === 0 ? (
              <Text style={styles.hint}>{t('rewards.empty')}</Text>
            ) : null}
            <Text style={styles.hint}>{t('rewards.recognitionNote')}</Text>
          </View>
        ) : null}
        <Button mode="contained" onPress={() => router.push('/leaderboard' as Href)}>
          {t('more.leaderboard')}
        </Button>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing.lg, gap: spacing.md },
  title: { fontSize: 24, fontWeight: '700', color: colors.brandDark },
  lede: { color: colors.textMuted },
  card: { backgroundColor: colors.surface, padding: spacing.lg, borderRadius: 16, gap: spacing.sm },
  hint: { color: colors.textMuted },
  error: { color: colors.danger },
});

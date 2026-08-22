import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { useI18n } from '@/i18n/LocaleProvider';
import { getMyRewards, type CitizenRewards } from '@/services/api/rewards';
import { colors, radii, spacing } from '@/theme';

export default function RewardsScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useCitizenAuth();
  const [data, setData] = useState<CitizenRewards | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setData(await getMyRewards());
    } catch (err) {
      setError(err instanceof Error ? err.message : t('rewards.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (isAuthenticated) void load();
  }, [isAuthenticated, load]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <View style={styles.centered}>
          <ActivityIndicator color={colors.brand} />
          <Text style={styles.hint}>{t('common.loading')}</Text>
        </View>
      </SafeAreaView>
    );
  }
  if (!isAuthenticated) return <Redirect href={buildLoginHref('/rewards') as Href} />;

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>{t('rewards.title')}</Text>
        <Text style={styles.lede}>{t('rewards.lede')}</Text>
        {loading && !data ? (
          <View style={styles.centered}>
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.hint}>{t('common.loading')}</Text>
          </View>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {data ? <RewardsBody data={data} /> : null}
        <Button mode="contained" onPress={() => router.push('/leaderboard' as Href)}>
          {t('rewards.openLeaderboard')}
        </Button>
      </ScrollView>
    </SafeAreaView>
  );
}

function RewardsBody({ data }: { data: CitizenRewards }) {
  const { t } = useI18n();
  const router = useRouter();
  const prompt = !data.participation.eligible
    ? data.participation.optedIn
      ? t('rewards.completeProfile')
      : t('rewards.privateBoard')
    : null;
  const events = data.recentEvents ?? [];
  const badges = data.badges ?? [];

  return (
    <>
      {prompt ? (
        <View style={styles.notice}>
          <Text style={styles.hint}>{prompt}</Text>
          <Button mode="text" onPress={() => router.push('/profile' as Href)}>
            {t('profile.title')}
          </Button>
        </View>
      ) : null}
      <View style={styles.card}>
        <Text>
          {t('rewards.confirmed')}: {data.confirmedPoints}
        </Text>
        <Text>
          {t('rewards.pending')}: {data.pendingPoints}
        </Text>
        {data.pendingPoints > 0 ? <Text style={styles.hint}>{t('rewards.pendingWhy')}</Text> : null}
        <Text>
          {t('rewards.monthly')}: {data.monthlyPoints}
        </Text>
        <Text>
          {t('rewards.level')}: {data.levelTitle}
        </Text>
        <Text>
          {t('rewards.rank')}: {data.privateRankAllTime ?? '—'}
        </Text>
        {data.publicRankAllTime ? (
          <Text>
            {t('rewards.publicRank')}: {data.publicRankAllTime}
          </Text>
        ) : null}
        <Text style={styles.hint}>
          {data.pointsToNextLevel != null && data.nextLevelTitle
            ? t('rewards.nextLevel', {
                points: data.pointsToNextLevel,
                title: data.nextLevelTitle,
              })
            : t('rewards.maxLevel')}
        </Text>
        <Text style={styles.section}>{t('rewards.badges')}</Text>
        {badges.length ? (
          badges.map((badge) => (
            <Text key={badge} style={styles.hint}>
              {badge}
            </Text>
          ))
        ) : (
          <Text style={styles.hint}>{t('rewards.noBadges')}</Text>
        )}
      </View>
      {data.confirmedPoints === 0 ? (
        <View style={styles.notice}>
          <Text style={styles.section}>{t('rewards.emptyTitle')}</Text>
          <Text style={styles.hint}>{t('rewards.emptyBody')}</Text>
        </View>
      ) : null}
      <View style={styles.card}>
        <Text style={styles.section}>{t('rewards.recent')}</Text>
        {events.length ? (
          events.map((event) => (
            <Text key={`${event.createdAt}-${event.reason}-${event.delta}`} style={styles.hint}>
              {event.delta > 0 ? '+' : ''}
              {event.delta} · {t(`rewards.reason.${event.reason}`)}
              {event.credit === 'pending' ? ` · ${t('rewards.pending')}` : ''}
              {event.ticketNumber ? ` · ${event.ticketNumber}` : ''}
            </Text>
          ))
        ) : (
          <Text style={styles.hint}>{t('rewards.emptyBody')}</Text>
        )}
      </View>
      <Text style={styles.hint}>{t('rewards.recognitionNote')}</Text>
    </>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing[5], gap: spacing[4] },
  centered: { alignItems: 'center', gap: spacing[3], paddingVertical: spacing[6] },
  title: { fontSize: 24, fontWeight: '700', color: colors.brandDark },
  lede: { color: colors.textMuted },
  card: {
    backgroundColor: colors.surface,
    padding: spacing[5],
    borderRadius: radii.md,
    gap: spacing[2],
  },
  notice: {
    backgroundColor: colors.surfaceSubtle,
    padding: spacing[4],
    borderRadius: radii.md,
    gap: spacing[2],
  },
  section: { fontWeight: '700', color: colors.brandDark, marginTop: spacing[2] },
  hint: { color: colors.textMuted },
  error: { color: colors.danger },
});

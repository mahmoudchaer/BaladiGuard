import { useCallback, useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useI18n } from '@/i18n/LocaleProvider';
import { getLeaderboard, type PublicLeaderboard, type RewardsPeriod } from '@/services/api/rewards';
import { colors, radii, spacing } from '@/theme';

export default function LeaderboardScreen() {
  const { t } = useI18n();
  const [period, setPeriod] = useState<RewardsPeriod>('all-time');
  const [page, setPage] = useState<PublicLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadGeneration = useRef(0);

  const load = useCallback(
    async (next?: string | null) => {
      const generation = loadGeneration.current + 1;
      loadGeneration.current = generation;
      setError(null);
      setLoading(true);
      try {
        const result = await getLeaderboard(period, next);
        if (generation !== loadGeneration.current) return;
        setPage((current) =>
          next && current ? { ...result, items: [...current.items, ...result.items] } : result,
        );
      } catch (err) {
        if (generation !== loadGeneration.current) return;
        setError(err instanceof Error ? err.message : t('leaderboard.loadFailed'));
      } finally {
        if (generation === loadGeneration.current) setLoading(false);
      }
    },
    [period, t],
  );

  useEffect(() => {
    setPage(null);
    void load();
  }, [load]);

  const items = page?.items ?? [];

  return (
    <SafeAreaView style={styles.safe} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>{t('leaderboard.title')}</Text>
        <Text style={styles.lede}>{t('leaderboard.lede')}</Text>
        <View style={styles.row}>
          <Button
            mode={period === 'all-time' ? 'contained' : 'outlined'}
            onPress={() => setPeriod('all-time')}
          >
            {t('leaderboard.allTime')}
          </Button>
          <Button
            mode={period === 'monthly' ? 'contained' : 'outlined'}
            onPress={() => setPeriod('monthly')}
          >
            {t('leaderboard.monthly')}
          </Button>
        </View>
        {error ? (
          <>
            <Text style={styles.error}>{error}</Text>
            <Button mode="outlined" onPress={() => void load()} testID="leaderboard-retry">
              {t('common.tryAgain')}
            </Button>
          </>
        ) : null}
        {loading && !items.length ? (
          <View style={styles.centered}>
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.lede}>{t('common.loading')}</Text>
          </View>
        ) : null}
        {!loading && !items.length && !error ? (
          <View style={styles.card}>
            <Text style={styles.section}>{t('leaderboard.emptyTitle')}</Text>
            <Text style={styles.lede}>{t('leaderboard.emptyBody')}</Text>
          </View>
        ) : null}
        {items.map((item) => (
          <View key={`${item.rank}-${item.displayName}-${item.points}`} style={styles.card}>
            <Text>
              {t('leaderboard.rank', { rank: item.rank })} · {item.displayName} ·{' '}
              {t('leaderboard.points', { points: item.points })} · {item.levelTitle}
            </Text>
          </View>
        ))}
        {page?.nextCursor ? (
          <Button disabled={loading} onPress={() => void load(page.nextCursor)}>
            {t('leaderboard.loadMore')}
          </Button>
        ) : null}
        <Text style={styles.lede}>{t('leaderboard.tieNote')}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing[5], gap: spacing[4] },
  centered: { alignItems: 'center', gap: spacing[3], paddingVertical: spacing[6] },
  title: { fontSize: 24, fontWeight: '700', color: colors.brandDark },
  lede: { color: colors.textMuted },
  section: { fontWeight: '700', color: colors.brandDark },
  row: { flexDirection: 'row', gap: spacing[2] },
  card: {
    backgroundColor: colors.surface,
    padding: spacing[4],
    borderRadius: radii.md,
    gap: spacing[2],
  },
  error: { color: colors.danger },
});

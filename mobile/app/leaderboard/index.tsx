import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useI18n } from '@/i18n/LocaleProvider';
import { getLeaderboard, type PublicLeaderboard, type RewardsPeriod } from '@/services/api/rewards';
import { colors, spacing } from '@/theme';

export default function LeaderboardScreen() {
  const { t } = useI18n();
  const [period, setPeriod] = useState<RewardsPeriod>('all-time');
  const [page, setPage] = useState<PublicLeaderboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (next?: string | null) => {
      setError(null);
      try {
        const result = await getLeaderboard(period, next);
        setPage((current) =>
          next && current ? { ...result, items: [...current.items, ...result.items] } : result,
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : t('leaderboard.loadFailed'));
      }
    },
    [period, t],
  );

  useEffect(() => {
    void load();
  }, [load]);

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
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {page && !page.items.length ? <Text>{t('leaderboard.empty')}</Text> : null}
        {page?.items.map((item) => (
          <View key={`${item.rank}-${item.displayName}`} style={styles.card}>
            <Text>
              #{item.rank} · {item.displayName} · {t('leaderboard.points', { points: item.points })}{' '}
              · {item.levelTitle}
            </Text>
          </View>
        ))}
        {page?.nextCursor ? (
          <Button onPress={() => void load(page.nextCursor)}>{t('leaderboard.loadMore')}</Button>
        ) : null}
        <Text style={styles.lede}>{t('leaderboard.tieNote')}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { padding: spacing[5], gap: spacing[4] },
  title: { fontSize: 24, fontWeight: '700', color: colors.brandDark },
  lede: { color: colors.textMuted },
  row: { flexDirection: 'row', gap: spacing[2] },
  card: { backgroundColor: colors.surface, padding: spacing[4], borderRadius: 12 },
  error: { color: colors.danger },
});

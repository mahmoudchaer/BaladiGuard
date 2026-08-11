import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { AppBottomNavigation } from '@/components/AppBottomNavigation';
import { StatusChip } from '@/components/StatusChip';
import {
  getCitizenTicketHistory,
  TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
} from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

const PAGE_SIZE = 20;

function formatDisplayDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

export default function CitizenTicketHistoryScreen() {
  const router = useRouter();
  const { accessToken, clearSessionLocally, isAuthenticated, isLoading } = useCitizenAuth();
  const [items, setItems] = useState<CitizenTicketHistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const didInitialLoad = useRef(false);

  const loadHistory = useCallback(
    async (cursor: string | null, mode: 'initial' | 'refresh' | 'more') => {
      if (!accessToken) {
        return;
      }
      if (mode === 'initial') {
        setIsInitialLoading(true);
      } else if (mode === 'refresh') {
        setIsRefreshing(true);
      } else {
        setIsLoadingMore(true);
      }
      setErrorMessage(null);

      try {
        const page = await getCitizenTicketHistory({
          accessToken,
          limit: PAGE_SIZE,
          cursor,
        });
        setItems((current) => (mode === 'more' ? [...current, ...page.items] : page.items));
        setNextCursor(page.nextCursor);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unable to load your report history right now.';
        setErrorMessage(message);
        if (message === TICKET_HISTORY_UNAUTHORIZED_MESSAGE) {
          await clearSessionLocally();
        }
      } finally {
        setIsInitialLoading(false);
        setIsRefreshing(false);
        setIsLoadingMore(false);
      }
    },
    [accessToken, clearSessionLocally],
  );

  useEffect(() => {
    if (isLoading || !isAuthenticated || didInitialLoad.current) {
      return;
    }
    didInitialLoad.current = true;
    void loadHistory(null, 'initial');
  }, [isAuthenticated, isLoading, loadHistory]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
        <View style={styles.centered} testID="history-auth-loading">
          <ActivityIndicator color={colors.brand} />
          <Text variant="bodyMedium" style={styles.muted}>
            Loading account...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href={buildLoginHref('/history') as Href} />;
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={() => void loadHistory(null, 'refresh')}
            colors={[colors.brand]}
            tintColor={colors.brand}
          />
        }
      >
        <View style={styles.header}>
          <Text variant="headlineMedium" style={styles.title} accessibilityRole="header">
            My Reports
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            Reports submitted from your signed-in account. Tap any report to see its full status
            timeline.
          </Text>
        </View>

        {errorMessage ? (
          <View style={styles.errorBlock}>
            <Banner
              visible
              icon="alert-circle-outline"
              style={styles.banner}
              testID="history-error"
            >
              {errorMessage}
            </Banner>
            <Button
              mode="outlined"
              onPress={() => void loadHistory(null, 'refresh')}
              textColor={colors.brandDark}
              style={styles.retryButton}
              testID="history-retry"
            >
              Try again
            </Button>
          </View>
        ) : null}

        {isInitialLoading ? (
          <View style={styles.centeredBlock} testID="history-loading">
            <ActivityIndicator color={colors.brand} />
            <Text variant="bodyMedium" style={styles.muted}>
              Loading your reports...
            </Text>
          </View>
        ) : null}

        {!isInitialLoading && items.length === 0 && !errorMessage ? (
          <View style={styles.emptyState} testID="history-empty">
            <Text variant="titleMedium" style={styles.emptyTitle}>
              No reports yet
            </Text>
            <Text variant="bodyMedium" style={styles.muted}>
              Reports you submit while signed in will appear here.
            </Text>
            <Button
              mode="contained"
              icon="clipboard-text-outline"
              onPress={() => router.push('/report' as Href)}
              style={styles.inlineButton}
              contentStyle={styles.controlContent}
              buttonColor={colors.brand}
              textColor={colors.textInverse}
            >
              Report an issue
            </Button>
          </View>
        ) : null}

        {items.length > 0 ? (
          <View style={styles.list}>
            {items.map((item) => (
              <Pressable
                key={`${item.trackingCode}-${item.submittedAt}`}
                style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
                onPress={() =>
                  router.push({
                    pathname: '/track',
                    params: { trackingCode: item.trackingCode },
                  })
                }
                testID={`history-open-${item.trackingCode}`}
                accessibilityRole="button"
                accessibilityLabel={`View report ${item.trackingCode}`}
              >
                <View style={styles.rowHeader}>
                  <Text variant="titleSmall" style={styles.trackingCode}>
                    {item.trackingCode}
                  </Text>
                  <StatusChip status={item.status} />
                </View>
                <Text variant="bodyMedium" style={styles.location} numberOfLines={2}>
                  {item.locationAddress}
                </Text>
                <Text variant="bodySmall" style={styles.muted}>
                  {formatCategoryLabel(item.category)} · Submitted{' '}
                  {formatDisplayDate(item.submittedAt)}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}

        {nextCursor ? (
          <Button
            mode="outlined"
            icon="chevron-down"
            onPress={() => void loadHistory(nextCursor, 'more')}
            loading={isLoadingMore}
            disabled={isLoadingMore}
            style={styles.inlineButton}
            textColor={colors.brandDark}
            testID="history-load-more"
          >
            {isLoadingMore ? 'Loading more...' : 'Load more'}
          </Button>
        ) : null}
      </ScrollView>
      <AppBottomNavigation active="history" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    padding: spacing[5],
    gap: spacing[4],
    paddingBottom: spacing[8],
  },
  header: {
    gap: spacing[2],
  },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    color: colors.textSecondary,
    lineHeight: 21,
  },
  muted: {
    color: colors.textMuted,
  },
  errorBlock: {
    gap: spacing[3],
  },
  banner: {
    borderRadius: radii.md,
    backgroundColor: colors.dangerSoft,
  },
  retryButton: {
    alignSelf: 'flex-start',
    borderColor: colors.brand,
    borderRadius: radii.md,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[3],
    padding: spacing[5],
  },
  centeredBlock: {
    alignItems: 'center',
    gap: spacing[3],
    paddingVertical: spacing[8],
  },
  emptyState: {
    gap: spacing[2],
    paddingVertical: spacing[4],
  },
  emptyTitle: {
    fontWeight: '700',
    color: colors.text,
  },
  list: {
    gap: spacing[2],
  },
  row: {
    gap: spacing[1],
    paddingVertical: spacing[3],
    paddingHorizontal: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    minHeight: touchTargetMin,
  },
  rowPressed: {
    backgroundColor: colors.brandSoft,
    borderColor: colors.brand,
  },
  rowHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing[2],
  },
  trackingCode: {
    color: colors.text,
    fontWeight: '700',
    flexShrink: 1,
  },
  location: {
    color: colors.text,
  },
  inlineButton: {
    alignSelf: 'flex-start',
    borderRadius: radii.md,
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
});

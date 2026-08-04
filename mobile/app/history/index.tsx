import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Card, Text } from 'react-native-paper';
import { Redirect, useRouter, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import {
  getCitizenTicketHistory,
  TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
} from '@/services/api/tickets';
import type { CitizenTicketHistoryItem } from '@/types/ticket';

const PAGE_SIZE = 20;

const STATUS_LABELS: Record<CitizenTicketHistoryItem['status'], string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

const CATEGORY_LABELS: Record<string, string> = {
  drainage: 'Drainage',
  noise: 'Noise',
  public_facilities: 'Public Facilities',
  road_damage: 'Road Damage',
  sidewalk_damage: 'Sidewalk Damage',
  street_lighting: 'Street Lighting',
  traffic_signal: 'Traffic Signal',
  waste: 'Waste',
  water_leak: 'Water Leak',
};

function formatDisplayDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

function formatCategory(category: string | null): string {
  if (!category) {
    return 'Pending review';
  }
  const normalizedCategory = category.toLowerCase();
  return (
    CATEGORY_LABELS[normalizedCategory] ??
    normalizedCategory
      .split('_')
      .filter(Boolean)
      .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
      .join(' ')
  );
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
          <ActivityIndicator />
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
          />
        }
      >
        <View style={styles.header}>
          <Text variant="headlineMedium" style={styles.title}>
            Report history
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            Reports submitted from your signed-in account.
          </Text>
        </View>

        {errorMessage ? (
          <Banner visible icon="alert-circle-outline" style={styles.banner} testID="history-error">
            {errorMessage}
          </Banner>
        ) : null}

        {isInitialLoading ? (
          <View style={styles.centeredBlock} testID="history-loading">
            <ActivityIndicator />
            <Text variant="bodyMedium" style={styles.muted}>
              Loading your reports...
            </Text>
          </View>
        ) : null}

        {!isInitialLoading && items.length === 0 ? (
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
            >
              Report an issue
            </Button>
          </View>
        ) : null}

        {items.map((item) => (
          <Card key={`${item.trackingCode}-${item.submittedAt}`} style={styles.card}>
            <Card.Content style={styles.cardContent}>
              <View style={styles.cardHeader}>
                <Text variant="titleMedium" style={styles.trackingCode}>
                  {item.trackingCode}
                </Text>
                <Text variant="labelLarge" style={styles.status}>
                  {STATUS_LABELS[item.status] ?? item.status}
                </Text>
              </View>
              <Text variant="bodyMedium" style={styles.location}>
                {item.locationAddress}
              </Text>
              <Text variant="bodySmall" style={styles.muted}>
                {formatCategory(item.category)} - Submitted {formatDisplayDate(item.submittedAt)}
              </Text>
              <Button
                mode="outlined"
                icon="magnify"
                onPress={() =>
                  router.push({
                    pathname: '/track',
                    params: { trackingCode: item.trackingCode },
                  })
                }
                style={styles.inlineButton}
                testID={`history-open-${item.trackingCode}`}
              >
                View details
              </Button>
            </Card.Content>
          </Card>
        ))}

        {nextCursor ? (
          <Button
            mode="outlined"
            icon="chevron-down"
            onPress={() => void loadHistory(nextCursor, 'more')}
            loading={isLoadingMore}
            disabled={isLoadingMore}
            style={styles.inlineButton}
            testID="history-load-more"
          >
            {isLoadingMore ? 'Loading more...' : 'Load more'}
          </Button>
        ) : null}
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
    padding: 24,
    gap: 16,
    paddingBottom: 48,
  },
  header: {
    gap: 8,
  },
  title: {
    fontWeight: '700',
    color: '#0F172A',
  },
  subtitle: {
    color: '#475569',
  },
  muted: {
    color: '#64748B',
  },
  banner: {
    borderRadius: 8,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: 24,
  },
  centeredBlock: {
    alignItems: 'center',
    gap: 12,
    paddingVertical: 32,
  },
  emptyState: {
    gap: 10,
    paddingVertical: 16,
  },
  emptyTitle: {
    fontWeight: '700',
    color: '#0F172A',
  },
  card: {
    borderRadius: 8,
  },
  cardContent: {
    gap: 10,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  trackingCode: {
    color: '#0F172A',
    fontWeight: '700',
  },
  status: {
    color: '#0F766E',
  },
  location: {
    color: '#334155',
  },
  inlineButton: {
    alignSelf: 'flex-start',
  },
});

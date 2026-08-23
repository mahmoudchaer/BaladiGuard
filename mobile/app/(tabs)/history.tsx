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
import { StatusChip } from '@/components/StatusChip';
import { ResolutionFeedbackCard } from '@/components/ResolutionFeedbackCard';
import { useI18n } from '@/i18n/LocaleProvider';
import {
  getCitizenTicketHistory,
  submitCitizenResolutionFeedback,
  TICKET_HISTORY_UNAUTHORIZED_MESSAGE,
} from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { formatCategoryLabel } from '@/theme/labels';
import type { CitizenTicketHistoryItem, ResolutionFeedbackStatus } from '@/types/ticket';

const PAGE_SIZE = 20;

function formatDisplayDate(isoDate: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

export default function CitizenTicketHistoryScreen() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const { accessToken, clearSessionLocally, isAuthenticated, isLoading } = useCitizenAuth();
  const [items, setItems] = useState<CitizenTicketHistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackErrorFor, setFeedbackErrorFor] = useState<string | null>(null);
  const [submittingFeedbackFor, setSubmittingFeedbackFor] = useState<Set<string>>(new Set());
  const didInitialLoad = useRef(false);
  const requestGeneration = useRef(0);
  const feedbackRequestsInFlight = useRef<Set<string>>(new Set());

  const loadHistory = useCallback(
    async (cursor: string | null, mode: 'initial' | 'refresh' | 'more') => {
      if (!accessToken) {
        return;
      }
      const generation = requestGeneration.current + 1;
      requestGeneration.current = generation;
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
        if (generation !== requestGeneration.current) return;
        setItems((current) => (mode === 'more' ? [...current, ...page.items] : page.items));
        setNextCursor(page.nextCursor);
      } catch (error) {
        if (generation !== requestGeneration.current) return;
        const message = error instanceof Error ? error.message : t('history.loadError');
        setErrorMessage(message);
        if (message === TICKET_HISTORY_UNAUTHORIZED_MESSAGE) {
          await clearSessionLocally();
        }
      } finally {
        if (generation !== requestGeneration.current) return;
        setIsInitialLoading(false);
        setIsRefreshing(false);
        setIsLoadingMore(false);
      }
    },
    [accessToken, clearSessionLocally, t],
  );

  const handleFeedback = async (
    trackingCode: string,
    status: ResolutionFeedbackStatus,
    note?: string,
  ) => {
    if (!accessToken || feedbackRequestsInFlight.current.has(trackingCode)) {
      return;
    }
    feedbackRequestsInFlight.current.add(trackingCode);
    setSubmittingFeedbackFor((current) => new Set(current).add(trackingCode));
    setFeedbackError(null);
    setFeedbackErrorFor(null);
    try {
      const result = await submitCitizenResolutionFeedback({
        accessToken,
        trackingCode,
        status,
        note,
      });
      setItems((current) =>
        current.map((item) =>
          item.trackingCode === trackingCode
            ? {
                ...item,
                canSubmitResolutionFeedback: result.canSubmit,
                resolutionFeedbackStatus: result.status,
              }
            : item,
        ),
      );
    } catch (error) {
      setFeedbackErrorFor(trackingCode);
      setFeedbackError(error instanceof Error ? error.message : t('history.feedbackError'));
    } finally {
      feedbackRequestsInFlight.current.delete(trackingCode);
      setSubmittingFeedbackFor((current) => {
        const next = new Set(current);
        next.delete(trackingCode);
        return next;
      });
    }
  };

  useEffect(() => {
    if (isLoading || !isAuthenticated || didInitialLoad.current) {
      return;
    }
    didInitialLoad.current = true;
    void loadHistory(null, 'initial');
  }, [isAuthenticated, isLoading, loadHistory]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
        <View style={styles.centered} testID="history-auth-loading">
          <ActivityIndicator color={colors.brand} />
          <Text variant="bodyMedium" style={styles.muted}>
            {t('history.loadingAccount')}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!isAuthenticated) {
    return <Redirect href={buildLoginHref('/history') as Href} />;
  }

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'left', 'right']}>
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
            {t('history.title')}
          </Text>
          <Text variant="bodyMedium" style={styles.subtitle}>
            {t('history.subtitle')}
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
              {t('history.tryAgain')}
            </Button>
          </View>
        ) : null}

        {isInitialLoading ? (
          <View style={styles.centeredBlock} testID="history-loading">
            <ActivityIndicator color={colors.brand} />
            <Text variant="bodyMedium" style={styles.muted}>
              {t('history.loading')}
            </Text>
          </View>
        ) : null}

        {!isInitialLoading && items.length === 0 && !errorMessage ? (
          <View style={styles.emptyState} testID="history-empty">
            <Text variant="titleMedium" style={styles.emptyTitle}>
              {t('history.emptyTitle')}
            </Text>
            <Text variant="bodyMedium" style={styles.muted}>
              {t('history.emptyBody')}
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
              {t('history.reportIssue')}
            </Button>
          </View>
        ) : null}

        {items.length > 0 ? (
          <View style={styles.list}>
            {items.map((item) => (
              <View key={`${item.trackingCode}-${item.submittedAt}`} style={styles.row}>
                <Pressable
                  style={({ pressed }) => [pressed && styles.rowPressed]}
                  onPress={() =>
                    router.push({
                      pathname: '/track',
                      params: { trackingCode: item.trackingCode },
                    })
                  }
                  testID={`history-open-${item.trackingCode}`}
                  accessibilityRole="button"
                  accessibilityLabel={t('history.viewReport', { code: item.trackingCode })}
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
                    {t('history.categorySubmitted', {
                      category: formatCategoryLabel(item.category),
                      date: formatDisplayDate(item.submittedAt, locale),
                    })}
                  </Text>
                </Pressable>
                {item.canSubmitResolutionFeedback || item.resolutionFeedbackStatus ? (
                  <ResolutionFeedbackCard
                    trackingCode={item.trackingCode}
                    feedback={{
                      trackingCode: item.trackingCode,
                      ticketStatus: item.status,
                      canSubmit: Boolean(item.canSubmitResolutionFeedback),
                      status: item.resolutionFeedbackStatus ?? null,
                      submittedAt: null,
                    }}
                    submitting={submittingFeedbackFor.has(item.trackingCode)}
                    errorMessage={feedbackErrorFor === item.trackingCode ? feedbackError : null}
                    onSubmit={(status, note) =>
                      void handleFeedback(item.trackingCode, status, note)
                    }
                  />
                ) : null}
              </View>
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
            {isLoadingMore ? t('history.loadingMore') : t('history.loadMore')}
          </Button>
        ) : null}
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
    writingDirection: 'ltr',
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

import { useCallback, useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, HelperText, Text, TextInput } from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { StatusChip } from '@/components/StatusChip';
import { TicketTimeline } from '@/components/TicketTimeline';
import {
  defaultTrackLookupValues,
  trackLookupSchema,
  type TrackLookupFormValues,
} from '@/schemas/trackLookupSchema';
import { getTicketByTrackingCode } from '@/services/api/tickets';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import { describeStatusMeaning, formatCategoryLabel } from '@/theme/labels';
import type { CitizenTicketResponse } from '@/types/ticket';
import { getCitizenNextAction } from '@/utils/reportGuidance';
import { normalizeTrackingCode } from '@/utils/trackingCode';

function formatDisplayDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(isoDate));
}

type TrackLookupFormProps = {
  initialTrackingCode?: string;
};

export function TrackLookupForm({ initialTrackingCode }: TrackLookupFormProps) {
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [result, setResult] = useState<CitizenTicketResponse | null>(null);
  const requestInFlight = useRef(false);
  const didAutoLookup = useRef(false);
  const lastAttempted = useRef<string | null>(null);

  const {
    control,
    handleSubmit,
    reset,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<TrackLookupFormValues>({
    resolver: zodResolver(trackLookupSchema),
    defaultValues: defaultTrackLookupValues,
    mode: 'onBlur',
  });

  const onSubmit = useCallback(async (values: TrackLookupFormValues) => {
    // Guard against double-taps while the button is still enabled briefly.
    if (requestInFlight.current) {
      return;
    }
    requestInFlight.current = true;
    lastAttempted.current = values.trackingCode;
    setLookupError(null);
    setResult(null);

    try {
      const ticket = await getTicketByTrackingCode(values.trackingCode);
      setResult(ticket);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Something went wrong. Please try again.';
      setLookupError(message);
    } finally {
      requestInFlight.current = false;
    }
  }, []);

  useEffect(() => {
    const normalized = normalizeTrackingCode(initialTrackingCode ?? '');
    if (!normalized || didAutoLookup.current) {
      return;
    }
    didAutoLookup.current = true;
    setValue('trackingCode', normalized, { shouldValidate: true });
    void onSubmit({ trackingCode: normalized });
  }, [initialTrackingCode, onSubmit, setValue]);

  const handleReset = () => {
    reset(defaultTrackLookupValues);
    setLookupError(null);
    setResult(null);
    requestInFlight.current = false;
  };

  const handleRetry = () => {
    if (lastAttempted.current) {
      void onSubmit({ trackingCode: lastAttempted.current });
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Track a report
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Enter the 6-character tracking code from your submission confirmation. We look it up
          directly on the BaladiGuard API — no staff login required.
        </Text>
      </View>

      {lookupError ? (
        <View style={styles.errorBlock}>
          <Banner visible icon="alert-circle-outline" style={styles.banner}>
            {lookupError}
          </Banner>
          {lastAttempted.current ? (
            <Button
              mode="outlined"
              onPress={handleRetry}
              disabled={isSubmitting}
              style={styles.retryButton}
              contentStyle={styles.controlContent}
              textColor={colors.brandDark}
              testID="track-lookup-retry"
            >
              Try again
            </Button>
          ) : null}
        </View>
      ) : null}

      <Controller
        control={control}
        name="trackingCode"
        render={({ field: { onChange, onBlur, value } }) => (
          <View>
            <TextInput
              label="Tracking code"
              mode="outlined"
              autoCapitalize="characters"
              autoCorrect={false}
              autoComplete="off"
              value={value}
              onBlur={onBlur}
              onChangeText={(text) => {
                onChange(text);
                if (lookupError) {
                  setLookupError(null);
                }
              }}
              error={Boolean(errors.trackingCode)}
              disabled={isSubmitting}
              maxLength={12}
              outlineColor={colors.border}
              activeOutlineColor={colors.brand}
              accessibilityLabel="Tracking code"
              testID="tracking-code-input"
            />
            <HelperText type="error" visible={Boolean(errors.trackingCode)}>
              {errors.trackingCode?.message}
            </HelperText>
          </View>
        )}
      />

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        disabled={isSubmitting}
        loading={isSubmitting}
        icon="magnify"
        style={styles.submitButton}
        contentStyle={styles.controlContent}
        labelStyle={styles.controlLabel}
        buttonColor={colors.brand}
        textColor={colors.textInverse}
        testID="track-lookup-submit"
      >
        {isSubmitting ? 'Looking up...' : 'Look up report'}
      </Button>

      {isSubmitting ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator color={colors.brand} />
          <Text variant="bodyMedium" style={styles.loadingText}>
            Looking up your report...
          </Text>
        </View>
      ) : null}

      {!result && !isSubmitting && !lookupError ? (
        <View style={styles.emptyHint}>
          <Text variant="bodySmall" style={styles.emptyHintText}>
            Your tracking code was shown on the confirmation screen when you submitted a report.
          </Text>
        </View>
      ) : null}

      {result ? (
        <View style={styles.resultBlock} testID="track-lookup-result">
          <Text variant="titleLarge" style={styles.resultTitle}>
            Report found
          </Text>

          <View style={styles.resultHeader}>
            <View style={styles.resultHeaderText}>
              <Text variant="labelLarge" style={styles.rowLabel}>
                Tracking code
              </Text>
              <Text variant="titleMedium" style={styles.rowValueStrong}>
                {result.trackingCode}
              </Text>
              {result.ticketNumber ? (
                <Text variant="bodyMedium" style={styles.rowValue}>
                  {result.ticketNumber}
                </Text>
              ) : null}
            </View>
            <StatusChip status={result.status} />
          </View>

          <View style={styles.meaningBlock}>
            <Text variant="labelLarge" style={styles.rowLabel}>
              What this means
            </Text>
            <Text variant="bodyMedium" style={styles.rowValue}>
              {describeStatusMeaning(result.status)}
            </Text>
          </View>

          <View style={styles.rowGrid}>
            {result.category ? (
              <View style={styles.row}>
                <Text variant="labelLarge" style={styles.rowLabel}>
                  Category
                </Text>
                <Text variant="bodyLarge" style={styles.rowValue}>
                  {formatCategoryLabel(result.category)}
                </Text>
              </View>
            ) : null}
            {result.location?.addressText ? (
              <View style={styles.row}>
                <Text variant="labelLarge" style={styles.rowLabel}>
                  Location
                </Text>
                <Text variant="bodyLarge" style={styles.rowValue}>
                  {result.location.addressText}
                </Text>
              </View>
            ) : null}
            <View style={styles.row}>
              <Text variant="labelLarge" style={styles.rowLabel}>
                Submitted
              </Text>
              <Text variant="bodyMedium" style={styles.rowValue}>
                {formatDisplayDate(result.createdAt)}
              </Text>
            </View>
            <View style={styles.row}>
              <Text variant="labelLarge" style={styles.rowLabel}>
                Last updated
              </Text>
              <Text variant="bodyMedium" style={styles.rowValue}>
                {formatDisplayDate(result.lastUpdatedAt)}
              </Text>
            </View>
            {result.department?.name ? (
              <View style={styles.row}>
                <Text variant="labelLarge" style={styles.rowLabel}>
                  Department
                </Text>
                <Text variant="bodyLarge" style={styles.rowValue}>
                  {result.department.name}
                </Text>
              </View>
            ) : null}
          </View>

          <View style={styles.guidance} testID="track-next-action">
            <Text variant="labelLarge" style={styles.guidanceLabel}>
              What happens next
            </Text>
            <Text variant="bodyMedium" style={styles.guidanceText}>
              {getCitizenNextAction(result.status)}
            </Text>
          </View>

          <Text variant="titleMedium" style={styles.timelineHeading}>
            Timeline
          </Text>
          <TicketTimeline
            variant="citizen"
            emptyMessage="No status updates are available for this report yet."
            history={(result.timeline ?? []).map((entry) => ({
              status: entry.status,
              changedAt: entry.changedAt,
            }))}
          />

          <Button
            mode="outlined"
            onPress={handleReset}
            style={styles.resetButton}
            contentStyle={styles.controlContent}
            textColor={colors.brandDark}
          >
            Look up another code
          </Button>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
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
  submitButton: {
    borderRadius: radii.md,
  },
  controlContent: {
    minHeight: touchTargetMin,
  },
  controlLabel: {
    fontSize: typography.control,
    fontWeight: '700',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[3],
  },
  loadingText: {
    color: colors.textSecondary,
  },
  emptyHint: {
    padding: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
    backgroundColor: colors.surfaceSubtle,
  },
  emptyHintText: {
    color: colors.textMuted,
  },
  resultBlock: {
    gap: spacing[4],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  resultTitle: {
    fontWeight: '700',
    color: colors.brandDark,
  },
  resultHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: spacing[3],
  },
  resultHeaderText: {
    gap: 2,
    flexShrink: 1,
  },
  meaningBlock: {
    gap: 2,
    padding: spacing[3],
    borderRadius: radii.md,
    backgroundColor: colors.infoSoft,
  },
  rowGrid: {
    gap: spacing[3],
  },
  row: {
    gap: 2,
  },
  rowLabel: {
    color: colors.textMuted,
    fontSize: typography.label,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  rowValue: {
    color: colors.text,
  },
  rowValueStrong: {
    color: colors.text,
    fontWeight: '700',
  },
  guidance: {
    gap: 4,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.brandSoft,
    backgroundColor: colors.brandSoft,
    padding: spacing[3],
  },
  guidanceLabel: {
    color: colors.brandDark,
  },
  guidanceText: {
    color: colors.text,
  },
  timelineHeading: {
    fontWeight: '700',
    color: colors.text,
  },
  resetButton: {
    alignSelf: 'flex-start',
    borderColor: colors.brand,
    borderRadius: radii.md,
  },
});

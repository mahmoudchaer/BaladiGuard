import { useCallback, useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Banner,
  Button,
  Card,
  HelperText,
  Text,
  TextInput,
} from 'react-native-paper';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { TicketTimeline } from '@/components/TicketTimeline';
import {
  defaultTrackLookupValues,
  trackLookupSchema,
  type TrackLookupFormValues,
} from '@/schemas/trackLookupSchema';
import { getTicketByTrackingCode } from '@/services/api/tickets';
import type { CitizenTicketResponse } from '@/types/ticket';
import { normalizeTrackingCode } from '@/utils/trackingCode';

const STATUS_LABELS: Record<CitizenTicketResponse['status'], string> = {
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

function formatCategory(category: string): string {
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

type TrackLookupFormProps = {
  initialTrackingCode?: string;
};

export function TrackLookupForm({ initialTrackingCode }: TrackLookupFormProps) {
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [result, setResult] = useState<CitizenTicketResponse | null>(null);
  const requestInFlight = useRef(false);
  const didAutoLookup = useRef(false);

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

  return (
    <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Track a report
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Enter the 6-character tracking code from your submission confirmation. We look it up
          directly on the BaladiGuard API. No staff login required.
        </Text>
      </View>

      <Banner visible={Boolean(lookupError)} icon="alert-circle-outline" style={styles.banner}>
        {lookupError}
      </Banner>

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
        testID="track-lookup-submit"
      >
        {isSubmitting ? 'Looking up...' : 'Look up report'}
      </Button>

      {isSubmitting ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator />
          <Text variant="bodyMedium">Looking up your report...</Text>
        </View>
      ) : null}

      {result ? (
        <Card style={styles.resultCard} testID="track-lookup-result">
          <Card.Content style={styles.resultContent}>
            <Text variant="titleLarge" style={styles.resultTitle}>
              Report found
            </Text>
            <View style={styles.resultRow}>
              <Text variant="labelLarge">Tracking code</Text>
              <Text variant="titleMedium">{result.trackingCode}</Text>
            </View>
            {result.ticketNumber ? (
              <View style={styles.resultRow}>
                <Text variant="labelLarge">Ticket number</Text>
                <Text variant="bodyLarge">{result.ticketNumber}</Text>
              </View>
            ) : null}
            <View style={styles.resultRow}>
              <Text variant="labelLarge">Status</Text>
              <Text variant="bodyLarge">{STATUS_LABELS[result.status] ?? result.status}</Text>
            </View>
            {result.category ? (
              <View style={styles.resultRow}>
                <Text variant="labelLarge">Category</Text>
                <Text variant="bodyLarge">{formatCategory(result.category)}</Text>
              </View>
            ) : null}
            {result.location?.addressText ? (
              <View style={styles.resultRow}>
                <Text variant="labelLarge">Location</Text>
                <Text variant="bodyLarge">{result.location.addressText}</Text>
              </View>
            ) : null}
            <View style={styles.resultRow}>
              <Text variant="labelLarge">Last updated</Text>
              <Text variant="bodyMedium">{formatDisplayDate(result.lastUpdatedAt)}</Text>
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

            <Button mode="outlined" onPress={handleReset} style={styles.resetButton}>
              Look up another code
            </Button>
          </Card.Content>
        </Card>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
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
  banner: {
    borderRadius: 8,
  },
  submitButton: {
    alignSelf: 'flex-start',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  resultCard: {
    marginTop: 8,
  },
  resultContent: {
    gap: 12,
  },
  resultTitle: {
    fontWeight: '700',
    color: '#0F766E',
  },
  resultRow: {
    gap: 2,
  },
  timelineHeading: {
    marginTop: 8,
    fontWeight: '700',
  },
  resetButton: {
    marginTop: 8,
    alignSelf: 'flex-start',
  },
});

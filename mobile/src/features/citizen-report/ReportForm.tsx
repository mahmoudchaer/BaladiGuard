import { useState } from 'react';
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

import { ContactFields } from '@/features/citizen-report/components/ContactFields';
import { LocationFields } from '@/features/citizen-report/components/LocationFields';
import { PhotoPickerField } from '@/features/citizen-report/components/PhotoPickerField';
import {
  defaultReportFormValues,
  reportFormSchema,
  type ReportFormValues,
} from '@/schemas/reportFormSchema';
import { submitReport } from '@/services/api/tickets';
import { appConfig } from '@/services/config';
import type { SubmitTicketResponse } from '@/types/ticket';

export function ReportForm() {
  const [selectedPlaceholderId, setSelectedPlaceholderId] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<SubmitTicketResponse | null>(null);

  const {
    control,
    handleSubmit,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: defaultReportFormValues,
    mode: 'onBlur',
  });

  const onSubmit = async (values: ReportFormValues) => {
    setSubmitError(null);

    try {
      const response = await submitReport(values);
      setSuccessResult(response);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Something went wrong. Please try again.';
      setSubmitError(message);
    }
  };

  const handleReset = () => {
    reset(defaultReportFormValues);
    setSelectedPlaceholderId('');
    setSubmitError(null);
    setSuccessResult(null);
  };

  if (successResult) {
    return (
      <Card style={styles.successCard}>
        <Card.Content style={styles.successContent}>
          <Text variant="headlineSmall" style={styles.successTitle}>
            Report submitted
          </Text>
          <Text variant="bodyMedium">{successResult.message}</Text>
          <View style={styles.successDetails}>
            <Text variant="titleMedium">Ticket number</Text>
            <Text variant="headlineMedium" style={styles.ticketNumber}>
              {successResult.ticketNumber}
            </Text>
            <Text variant="bodySmall" style={styles.trackingHint}>
              Save this number to track your report later.
            </Text>
            <Text variant="labelLarge" style={styles.trackingLabel}>
              Tracking code
            </Text>
            <Text variant="titleLarge">{successResult.trackingCode}</Text>
          </View>
          <Button mode="contained" onPress={handleReset}>
            Submit another report
          </Button>
        </Card.Content>
      </Card>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          Report an issue
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Tell us about an infrastructure problem in your area. Required fields are marked
          through validation when you submit.
        </Text>
      </View>

      {appConfig.enableMockApi ? (
        <Banner visible icon="information">
          Mock mode is enabled. Submissions return a sample ticket without calling the backend.
        </Banner>
      ) : null}

      {submitError ? (
        <Banner visible icon="alert-circle" style={styles.errorBanner}>
          {submitError}
        </Banner>
      ) : null}

      <View style={styles.section}>
        <Text variant="titleMedium" style={styles.label}>
          Description
        </Text>
        <Controller
          control={control}
          name="description"
          render={({ field: { value, onChange, onBlur } }) => (
            <TextInput
              mode="outlined"
              label="What is the problem?"
              placeholder="Describe the pothole, broken light, waste pile, etc."
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              multiline
              numberOfLines={5}
              style={styles.textArea}
              error={Boolean(errors.description)}
            />
          )}
        />
        {errors.description ? (
          <HelperText type="error" visible>
            {errors.description.message}
          </HelperText>
        ) : null}
      </View>

      <View style={styles.section}>
        <PhotoPickerField control={control} errors={errors} setValue={setValue} />
      </View>

      <View style={styles.section}>
        <ContactFields control={control} errors={errors} />
      </View>

      <View style={styles.section}>
        <LocationFields
          control={control}
          errors={errors}
          setValue={setValue}
          selectedPlaceholderId={selectedPlaceholderId}
          onSelectPlaceholder={setSelectedPlaceholderId}
        />
      </View>

      <Button
        mode="contained"
        onPress={handleSubmit(onSubmit)}
        disabled={isSubmitting}
        style={styles.submitButton}
        contentStyle={styles.submitButtonContent}
      >
        {isSubmitting ? <ActivityIndicator animating color="#FFFFFF" /> : 'Submit report'}
      </Button>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
    gap: 20,
  },
  header: {
    gap: 8,
  },
  title: {
    fontWeight: '700',
  },
  subtitle: {
    color: '#475569',
  },
  section: {
    gap: 8,
  },
  label: {
    fontWeight: '600',
  },
  textArea: {
    minHeight: 140,
  },
  submitButton: {
    marginTop: 8,
  },
  submitButtonContent: {
    paddingVertical: 6,
  },
  errorBanner: {
    backgroundColor: '#FEF2F2',
  },
  successCard: {
    margin: 20,
  },
  successContent: {
    gap: 16,
  },
  successTitle: {
    fontWeight: '700',
  },
  successDetails: {
    gap: 6,
    paddingVertical: 8,
  },
  ticketNumber: {
    color: '#0B5FFF',
    fontWeight: '700',
  },
  trackingHint: {
    color: '#64748B',
    marginBottom: 8,
  },
  trackingLabel: {
    marginTop: 4,
  },
});

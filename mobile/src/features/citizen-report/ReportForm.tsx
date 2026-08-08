import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, Text } from 'react-native-paper';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useCitizenAuth } from '@/auth';
import { DetailsStep } from '@/features/citizen-report/components/DetailsStep';
import { LocationFields } from '@/features/citizen-report/components/LocationFields';
import { PhotoPickerField } from '@/features/citizen-report/components/PhotoPickerField';
import { ReportSuccess } from '@/features/citizen-report/components/ReportSuccess';
import { ReviewSummary } from '@/features/citizen-report/components/ReviewSummary';
import {
  REPORT_WIZARD_STEP_ORDER,
  StepProgress,
  type ReportWizardStepKey,
} from '@/features/citizen-report/components/StepProgress';
import {
  defaultReportFormValues,
  reportFormSchema,
  type ReportFormValues,
} from '@/schemas/reportFormSchema';
import { submitReport, type SubmitReportPhase } from '@/services/api/tickets';
import { appConfig } from '@/services/config';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { SubmitTicketResponse } from '@/types/ticket';

const submitPhaseLabels: Record<SubmitReportPhase, string> = {
  'uploading-photo': 'Uploading photo...',
  'submitting-report': 'Submitting report...',
};

/** Fields validated before a step is allowed to advance. */
const STEP_FIELDS: Record<ReportWizardStepKey, Array<keyof ReportFormValues>> = {
  details: ['description'],
  photo: ['photoUri'],
  location: ['addressText', 'latitude', 'longitude'],
  review: [],
};

const STEP_TITLES: Record<ReportWizardStepKey, string> = {
  details: 'Report an issue',
  photo: 'Add a photo',
  location: 'Where is it?',
  review: 'Review your report',
};

const STEP_SUBTITLES: Record<ReportWizardStepKey, string> = {
  details: 'Tell us about an infrastructure problem in your area. It only takes a minute.',
  photo: 'A clear photo helps crews confirm and prioritize the issue.',
  location: 'We use this to route your report to the right department.',
  review: 'Make sure everything looks right, then send it in.',
};

export function ReportForm() {
  const { profile } = useCitizenAuth();
  const [step, setStep] = useState<ReportWizardStepKey>('details');
  const [selectedPlaceholderId, setSelectedPlaceholderId] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitPhase, setSubmitPhase] = useState<SubmitReportPhase | null>(null);
  const [successResult, setSuccessResult] = useState<SubmitTicketResponse | null>(null);

  const {
    control,
    handleSubmit,
    setValue,
    trigger,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: defaultReportFormValues,
    mode: 'onBlur',
  });

  const stepIndex = REPORT_WIZARD_STEP_ORDER.indexOf(step);

  const goToStep = (target: ReportWizardStepKey) => {
    setStep(target);
  };

  const goBack = () => {
    if (stepIndex > 0) {
      setStep(REPORT_WIZARD_STEP_ORDER[stepIndex - 1]);
    }
  };

  const goNext = async () => {
    const fields = STEP_FIELDS[step];
    const isValid = fields.length > 0 ? await trigger(fields) : true;
    if (!isValid) {
      return;
    }
    if (stepIndex < REPORT_WIZARD_STEP_ORDER.length - 1) {
      setStep(REPORT_WIZARD_STEP_ORDER[stepIndex + 1]);
    }
  };

  const onSubmit = async (values: ReportFormValues) => {
    setSubmitError(null);
    setSubmitPhase(appConfig.enableMockApi ? null : 'uploading-photo');

    try {
      const response = await submitReport(values, {
        onProgress: setSubmitPhase,
      });
      setSuccessResult(response);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Something went wrong. Please try again.';
      setSubmitError(message);
    } finally {
      setSubmitPhase(null);
    }
  };

  const handleReset = () => {
    reset(defaultReportFormValues);
    setSelectedPlaceholderId('');
    setSubmitError(null);
    setSubmitPhase(null);
    setSuccessResult(null);
    setStep('details');
  };

  if (successResult) {
    return (
      <ScrollView contentContainerStyle={styles.successScroll} keyboardShouldPersistTaps="handled">
        <ReportSuccess result={successResult} onReportAnother={handleReset} />
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text variant="headlineMedium" style={styles.title}>
          {STEP_TITLES[step]}
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          {STEP_SUBTITLES[step]}
        </Text>
      </View>

      <StepProgress currentStep={step} />

      {appConfig.enableMockApi ? (
        <Banner visible icon="information">
          Mock mode is enabled. Submissions return a sample ticket without calling the backend.
        </Banner>
      ) : null}

      {step === 'review' && submitError ? (
        <Banner visible icon="alert-circle" style={styles.errorBanner}>
          {submitError}
        </Banner>
      ) : null}

      <View style={styles.stepContent}>
        {step === 'details' ? <DetailsStep control={control} errors={errors} /> : null}

        {step === 'photo' ? (
          <PhotoPickerField control={control} errors={errors} setValue={setValue} />
        ) : null}

        {step === 'location' ? (
          <>
            <View style={styles.identityNotice} testID="verified-identity-notice">
              <Text variant="labelLarge">Verified contributor</Text>
              <Text variant="bodyMedium" style={styles.identityText}>
                {profile?.fullName
                  ? `${profile.fullName} is signed in by verified phone. Contact details are taken from your profile.`
                  : 'You are signed in by verified phone. Contact details are taken from your profile.'}
              </Text>
            </View>
            <LocationFields
              control={control}
              errors={errors}
              setValue={setValue}
              selectedPlaceholderId={selectedPlaceholderId}
              onSelectPlaceholder={setSelectedPlaceholderId}
            />
          </>
        ) : null}

        {step === 'review' ? <ReviewSummary control={control} onEditStep={goToStep} /> : null}
      </View>

      <View style={styles.navRow}>
        {stepIndex > 0 ? (
          <Button
            mode="outlined"
            onPress={goBack}
            disabled={isSubmitting}
            style={styles.navButton}
            contentStyle={styles.navButtonContent}
            textColor={colors.brandDark}
          >
            Back
          </Button>
        ) : null}

        {step === 'review' ? (
          <Button
            mode="contained"
            onPress={handleSubmit(onSubmit)}
            disabled={isSubmitting}
            style={[styles.navButton, styles.primaryNavButton]}
            contentStyle={styles.navButtonContent}
          >
            {isSubmitting ? (
              <View style={styles.submittingContent}>
                <ActivityIndicator animating color={colors.textInverse} />
                <Text style={styles.submittingText}>
                  {submitPhaseLabels[submitPhase ?? 'uploading-photo']}
                </Text>
              </View>
            ) : (
              'Submit report'
            )}
          </Button>
        ) : (
          <Button
            mode="contained"
            onPress={() => {
              void goNext();
            }}
            style={[styles.navButton, styles.primaryNavButton]}
            contentStyle={styles.navButtonContent}
          >
            Continue
          </Button>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    padding: spacing[5],
    paddingBottom: spacing[8],
    gap: spacing[5],
  },
  successScroll: {
    flexGrow: 1,
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
  },
  stepContent: {
    gap: spacing[5],
  },
  identityNotice: {
    gap: spacing[1],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.infoSoft,
    padding: spacing[3],
  },
  identityText: {
    color: colors.textSecondary,
  },
  navRow: {
    flexDirection: 'row',
    gap: spacing[3],
    marginTop: spacing[2],
  },
  navButton: {
    borderRadius: radii.md,
    flexGrow: 1,
  },
  primaryNavButton: {
    flexGrow: 2,
  },
  navButtonContent: {
    minHeight: touchTargetMin,
  },
  submittingContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing[2],
  },
  submittingText: {
    color: colors.textInverse,
    fontWeight: '600',
    fontSize: typography.bodyCompact,
  },
  errorBanner: {
    backgroundColor: colors.dangerSoft,
  },
});

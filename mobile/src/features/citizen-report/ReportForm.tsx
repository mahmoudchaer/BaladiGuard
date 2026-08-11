import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, Text } from 'react-native-paper';
import { useForm, useWatch } from 'react-hook-form';
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
import { submitReport, SubmitReportError, type SubmitReportPhase } from '@/services/api/tickets';
import { appConfig } from '@/services/config';
import {
  buildReportDraft,
  clearReportDraft,
  clearUnusableDraftPhoto,
  createClientSubmissionId,
  draftHasRestorableContent,
  draftToFormValues,
  loadReportDraft,
  saveReportDraft,
  type ReportDraft,
  type ReportDraftSubmissionState,
} from '@/services/reportDraft';
import { checkLocalPhotoUri, PHOTO_REFERENCE_EXPIRED_MESSAGE } from '@/services/photoReference';
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

const DRAFT_SAVE_DEBOUNCE_MS = 450;

export function ReportForm() {
  const { profile } = useCitizenAuth();
  const ownerUserId = profile?.userId ?? null;

  const [step, setStep] = useState<ReportWizardStepKey>('details');
  const [returnToReview, setReturnToReview] = useState(false);
  const [selectedPlaceholderId, setSelectedPlaceholderId] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitPhase, setSubmitPhase] = useState<SubmitReportPhase | null>(null);
  const [successResult, setSuccessResult] = useState<SubmitTicketResponse | null>(null);
  const [pendingDraft, setPendingDraft] = useState<ReportDraft | null>(null);
  const [draftBanner, setDraftBanner] = useState<string | null>(null);
  const [draftSaveError, setDraftSaveError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<ReportDraftSubmissionState | null>(null);
  const [draftHydrated, setDraftHydrated] = useState(false);

  const {
    control,
    handleSubmit,
    setValue,
    trigger,
    reset,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<ReportFormValues>({
    resolver: zodResolver(reportFormSchema),
    defaultValues: defaultReportFormValues,
    mode: 'onBlur',
  });

  const watchedValues = useWatch({ control });
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const skipNextAutosaveRef = useRef(false);

  const persistDraft = useCallback(
    async (
      nextStep: ReportWizardStepKey,
      form: ReportFormValues,
      nextSubmission: ReportDraftSubmissionState | null,
      placeholderId: string,
    ) => {
      if (!ownerUserId) {
        return;
      }
      try {
        const draft = buildReportDraft({
          ownerUserId,
          step: nextStep,
          form,
          selectedPlaceholderId: placeholderId,
          submission: nextSubmission ?? undefined,
        });
        if (!draftHasRestorableContent(draft)) {
          await clearReportDraft(ownerUserId);
          setDraftSaveError(null);
          return;
        }
        await saveReportDraft(draft);
        setDraftSaveError(null);
      } catch {
        setDraftSaveError(
          'Could not save your draft on this device. You can keep editing, but progress may be lost if you leave.',
        );
      }
    },
    [ownerUserId],
  );

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      if (!ownerUserId) {
        if (!cancelled) {
          setPendingDraft(null);
          setDraftHydrated(true);
        }
        return;
      }
      try {
        const stored = await loadReportDraft(ownerUserId);
        if (cancelled) {
          return;
        }
        if (stored && draftHasRestorableContent(stored)) {
          setPendingDraft(stored);
        } else {
          setPendingDraft(null);
        }
      } finally {
        if (!cancelled) {
          setDraftHydrated(true);
        }
      }
    }
    setDraftHydrated(false);
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [ownerUserId]);

  useEffect(() => {
    if (!draftHydrated || !ownerUserId || pendingDraft || successResult) {
      return;
    }
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false;
      return;
    }
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = setTimeout(() => {
      void persistDraft(step, getValues(), submission, selectedPlaceholderId);
    }, DRAFT_SAVE_DEBOUNCE_MS);
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [
    watchedValues,
    step,
    selectedPlaceholderId,
    submission,
    ownerUserId,
    draftHydrated,
    pendingDraft,
    successResult,
    persistDraft,
    getValues,
  ]);

  const restorePendingDraft = () => {
    if (!pendingDraft) {
      return;
    }
    void (async () => {
      skipNextAutosaveRef.current = true;
      let draft = pendingDraft;
      let notice: string | null = null;
      const hasLocalPhoto = draft.form.photoUri.trim().length > 0;
      const hasUploadedKey = Boolean(draft.submission?.imageObjectKey);

      if (hasLocalPhoto) {
        const photoCheck = await checkLocalPhotoUri(draft.form.photoUri);
        if (!photoCheck.ok) {
          draft = clearUnusableDraftPhoto(draft);
          if (ownerUserId) {
            await saveReportDraft(draft);
          }
          notice = hasUploadedKey
            ? `${PHOTO_REFERENCE_EXPIRED_MESSAGE} A photo was already uploaded for this attempt — you can resubmit without re-picking, or attach a new photo.`
            : PHOTO_REFERENCE_EXPIRED_MESSAGE;
        }
      }

      const values = draftToFormValues(draft);
      if (!notice) {
        if (!values.photoUri.trim() && hasUploadedKey) {
          notice =
            'Draft restored. A photo was already uploaded for this attempt — you can resubmit without re-picking if the form still has a photo, or attach again if it is missing.';
        } else if (!values.photoUri.trim() && !hasUploadedKey) {
          notice =
            'Draft restored, but no local photo was saved. Attach a photo again before submitting.';
        } else {
          notice = 'Draft restored. You can continue or discard it.';
        }
      }

      reset(values);
      setStep(draft.step);
      setSelectedPlaceholderId(draft.selectedPlaceholderId ?? '');
      setSubmission(draft.submission ?? null);
      setPendingDraft(null);
      setDraftBanner(notice);
      setSubmitError(null);
    })();
  };

  const discardPendingDraft = async () => {
    if (ownerUserId) {
      await clearReportDraft(ownerUserId);
    }
    setPendingDraft(null);
    setSubmission(null);
    setDraftBanner(null);
  };

  const discardActiveDraft = () => {
    Alert.alert(
      'Discard draft?',
      'This clears the saved report draft on this device. You cannot undo this.',
      [
        { text: 'Keep editing', style: 'cancel' },
        {
          text: 'Discard',
          style: 'destructive',
          onPress: () => {
            void (async () => {
              if (ownerUserId) {
                await clearReportDraft(ownerUserId);
              }
              skipNextAutosaveRef.current = true;
              reset(defaultReportFormValues);
              setSelectedPlaceholderId('');
              setSubmitError(null);
              setSubmitPhase(null);
              setSuccessResult(null);
              setReturnToReview(false);
              setStep('details');
              setSubmission(null);
              setDraftBanner(null);
            })();
          },
        },
      ],
    );
  };

  const stepIndex = REPORT_WIZARD_STEP_ORDER.indexOf(step);

  const goToStep = (target: ReportWizardStepKey) => {
    setReturnToReview(step === 'review');
    setStep(target);
  };

  const goBack = () => {
    if (returnToReview) {
      setReturnToReview(false);
      setStep('review');
      return;
    }
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
    if (returnToReview) {
      setReturnToReview(false);
      setStep('review');
      return;
    }
    if (stepIndex < REPORT_WIZARD_STEP_ORDER.length - 1) {
      setStep(REPORT_WIZARD_STEP_ORDER[stepIndex + 1]);
    }
  };

  const onSubmit = async (values: ReportFormValues) => {
    setSubmitError(null);
    setSubmitPhase(appConfig.enableMockApi ? null : 'uploading-photo');
    const clientSubmissionId = submission?.clientSubmissionId ?? createClientSubmissionId();
    const nextSubmission: ReportDraftSubmissionState = {
      clientSubmissionId,
      imageObjectKey: submission?.imageObjectKey,
    };
    setSubmission(nextSubmission);
    await persistDraft('review', values, nextSubmission, selectedPlaceholderId);

    try {
      const response = await submitReport(values, {
        onProgress: setSubmitPhase,
        clientSubmissionId,
        imageObjectKey: nextSubmission.imageObjectKey,
        onPartialState: (partial) => {
          const updated: ReportDraftSubmissionState = {
            clientSubmissionId: partial.clientSubmissionId,
            imageObjectKey: partial.imageObjectKey,
          };
          setSubmission(updated);
          void persistDraft('review', values, updated, selectedPlaceholderId);
        },
      });
      if (ownerUserId) {
        await clearReportDraft(ownerUserId);
      }
      setSubmission(null);
      setDraftBanner(null);
      setSuccessResult(response);
    } catch (error) {
      if (error instanceof SubmitReportError) {
        const updated: ReportDraftSubmissionState = {
          clientSubmissionId: error.clientSubmissionId ?? clientSubmissionId,
          imageObjectKey: error.imageObjectKey ?? nextSubmission.imageObjectKey,
        };
        setSubmission(updated);
        void persistDraft('review', values, updated, selectedPlaceholderId);
        setSubmitError(error.message);
      } else {
        const message =
          error instanceof Error ? error.message : 'Something went wrong. Please try again.';
        setSubmitError(message);
      }
    } finally {
      setSubmitPhase(null);
    }
  };

  const handleReset = () => {
    skipNextAutosaveRef.current = true;
    reset(defaultReportFormValues);
    setSelectedPlaceholderId('');
    setSubmitError(null);
    setSubmitPhase(null);
    setSuccessResult(null);
    setReturnToReview(false);
    setStep('details');
    setSubmission(null);
    setDraftBanner(null);
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

      {pendingDraft ? (
        <Banner
          visible
          icon="content-save-outline"
          style={styles.draftBanner}
          testID="draft-restore-banner"
        >
          <Text variant="bodyMedium" style={styles.draftBannerText}>
            You have an unfinished report on this device. Restore it to continue, or discard and
            start fresh.
          </Text>
          <View style={styles.draftActions}>
            <Button mode="contained" onPress={restorePendingDraft} testID="draft-restore-button">
              Restore draft
            </Button>
            <Button
              mode="outlined"
              onPress={() => void discardPendingDraft()}
              testID="draft-discard-offer-button"
            >
              Discard
            </Button>
          </View>
        </Banner>
      ) : null}

      {draftBanner ? (
        <Banner visible icon="check-circle-outline" testID="draft-status-banner">
          {draftBanner}
        </Banner>
      ) : null}

      {draftSaveError ? (
        <Banner visible icon="alert" style={styles.errorBanner} testID="draft-save-error">
          {draftSaveError}
        </Banner>
      ) : null}

      {step === 'review' && submitError ? (
        <Banner visible icon="alert-circle" style={styles.errorBanner} testID="submit-error-banner">
          {submitError}
        </Banner>
      ) : null}

      {submission?.imageObjectKey && !successResult ? (
        <Banner visible icon="cloud-check-outline" testID="partial-upload-banner">
          Photo already uploaded for this attempt. Retry uses the same server photo and will not
          create a duplicate ticket.
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
            disabled={isSubmitting || Boolean(pendingDraft)}
            style={[styles.navButton, styles.primaryNavButton]}
            contentStyle={styles.navButtonContent}
            testID="submit-report-button"
          >
            {isSubmitting ? (
              <View style={styles.submittingContent}>
                <ActivityIndicator animating color={colors.textInverse} />
                <Text style={styles.submittingText}>
                  {submitPhaseLabels[submitPhase ?? 'uploading-photo']}
                </Text>
              </View>
            ) : submitError ? (
              'Retry submit'
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
            disabled={Boolean(pendingDraft)}
            style={[styles.navButton, styles.primaryNavButton]}
            contentStyle={styles.navButtonContent}
          >
            {returnToReview ? 'Back to review' : 'Continue'}
          </Button>
        )}
      </View>

      {!pendingDraft && !successResult ? (
        <Button
          mode="text"
          onPress={discardActiveDraft}
          textColor={colors.textMuted}
          testID="discard-draft-button"
        >
          Discard draft
        </Button>
      ) : null}
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
  draftBanner: {
    backgroundColor: colors.brandSoft,
    gap: spacing[2],
  },
  draftBannerText: {
    color: colors.text,
    marginBottom: spacing[2],
  },
  draftActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
    marginTop: spacing[2],
  },
});

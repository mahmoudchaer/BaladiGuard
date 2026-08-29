import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Banner, Button, Icon, Text } from 'react-native-paper';
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
  reportFormSchemaWithUploadedPhoto,
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
import { checkLocalPhotoUri } from '@/services/photoReference';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { SubmitTicketResponse } from '@/types/ticket';

function submitPhaseLabel(phase: SubmitReportPhase, translate: (key: string) => string): string {
  return phase === 'submitting-report'
    ? translate('report.submittingReport')
    : translate('report.uploadingPhoto');
}

/** Fields validated before a step is allowed to advance. */
const STEP_FIELDS: Record<ReportWizardStepKey, Array<keyof ReportFormValues>> = {
  details: ['description'],
  photo: ['photoUri'],
  location: ['addressText', 'latitude', 'longitude'],
  review: [],
};

const STEP_TITLE_KEYS: Record<ReportWizardStepKey, string> = {
  details: 'report.stepDetails',
  photo: 'report.stepPhoto',
  location: 'report.stepLocation',
  review: 'report.stepReview',
};

const STEP_SUBTITLE_KEYS: Record<ReportWizardStepKey, string> = {
  details: 'report.stepDetailsSubtitle',
  photo: 'report.stepPhotoSubtitle',
  location: 'report.stepLocationSubtitle',
  review: 'report.stepReviewSubtitle',
};

const DRAFT_SAVE_DEBOUNCE_MS = 450;

export function ReportForm() {
  const { t } = useI18n();
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
    resolver: zodResolver(
      submission?.imageObjectKey ? reportFormSchemaWithUploadedPhoto : reportFormSchema,
    ),
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
        setDraftSaveError(t('report.draftSaveFailed'));
      }
    },
    [ownerUserId, t],
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
            ? t('report.draftPhotoExpiredUploaded')
            : t('report.draftPhotoExpired');
        }
      }

      const values = draftToFormValues(draft);
      if (!notice) {
        if (!values.photoUri.trim() && hasUploadedKey) {
          notice = t('report.draftRestoredUploaded');
        } else if (!values.photoUri.trim() && !hasUploadedKey) {
          notice = t('report.draftRestoredNoPhoto');
        } else {
          notice = t('report.draftRestored');
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
    Alert.alert(t('report.discardTitle'), t('report.discardBody'), [
      { text: t('report.keepEditing'), style: 'cancel' },
      {
        text: t('report.discard'),
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
    ]);
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

  const invalidateUploadedPhoto = () => {
    setSubmission((current) =>
      current ? { clientSubmissionId: current.clientSubmissionId } : current,
    );
    setDraftBanner(null);
    setSubmitError(null);
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
        const message = error instanceof Error ? error.message : t('errors.generic');
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
          {t(STEP_TITLE_KEYS[step])}
        </Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          {t(STEP_SUBTITLE_KEYS[step])}
        </Text>
      </View>

      <StepProgress currentStep={step} />

      {appConfig.enableMockApi ? (
        <Banner visible icon="information">
          {t('report.mockMode')}
        </Banner>
      ) : null}

      {pendingDraft ? (
        <View style={styles.draftCard} testID="draft-restore-banner">
          <View style={styles.draftHeading}>
            <View style={styles.draftIcon}>
              <Icon source="content-save-outline" size={23} color={colors.brandDark} />
            </View>
            <View style={styles.draftCopy}>
              <Text style={styles.draftTitle}>{t('report.continueDraft')}</Text>
              <Text style={styles.draftBannerText}>{t('report.unfinishedSaved')}</Text>
            </View>
          </View>
          <View style={styles.draftActions}>
            <Button
              mode="contained"
              onPress={restorePendingDraft}
              style={styles.draftPrimaryAction}
              contentStyle={styles.draftActionContent}
              testID="draft-restore-button"
            >
              {t('report.restoreDraft')}
            </Button>
            <Button
              mode="text"
              onPress={() => void discardPendingDraft()}
              contentStyle={styles.draftActionContent}
              testID="draft-discard-offer-button"
            >
              {t('report.startOver')}
            </Button>
          </View>
        </View>
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

      {submission?.imageObjectKey && !successResult && !isSubmitting ? (
        <Banner visible icon="cloud-check-outline" testID="partial-upload-banner">
          {t('report.photoSaved')}
        </Banner>
      ) : null}

      <View style={styles.stepContent}>
        {step === 'details' ? <DetailsStep control={control} errors={errors} /> : null}

        {step === 'photo' ? (
          <PhotoPickerField
            control={control}
            errors={errors}
            setValue={setValue}
            onPhotoChanged={invalidateUploadedPhoto}
          />
        ) : null}

        {step === 'location' ? (
          <>
            <View style={styles.identityNotice} testID="verified-identity-notice">
              <Text variant="labelLarge">{t('report.verifiedContributor')}</Text>
              <Text variant="bodyMedium" style={styles.identityText}>
                {profile?.fullName
                  ? t('report.signedInNamed', { name: profile.fullName })
                  : t('report.signedInPhone')}
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

        {step === 'review' ? (
          <ReviewSummary
            control={control}
            onEditStep={goToStep}
            hasUploadedPhoto={Boolean(submission?.imageObjectKey)}
          />
        ) : null}
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
            {t('common.back')}
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
                  {submitPhaseLabel(submitPhase ?? 'uploading-photo', t)}
                </Text>
              </View>
            ) : submitError ? (
              t('report.retrySubmit')
            ) : (
              t('report.submit')
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
            {returnToReview ? t('report.backToReview') : t('report.continue')}
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
          {t('report.discardDraft')}
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
  draftCard: {
    padding: spacing[4],
    gap: spacing[4],
    borderRadius: radii.lg,
    backgroundColor: colors.surface,
  },
  draftHeading: { flexDirection: 'row', alignItems: 'center', gap: spacing[3] },
  draftIcon: {
    width: 42,
    height: 42,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brandSoft,
  },
  draftCopy: { flex: 1, gap: 2 },
  draftTitle: { fontSize: 16, fontWeight: '700', color: colors.text },
  draftBannerText: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
  },
  draftActions: {
    flexDirection: 'row',
    gap: spacing[2],
  },
  draftPrimaryAction: { flex: 1 },
  draftActionContent: { minHeight: touchTargetMin },
});

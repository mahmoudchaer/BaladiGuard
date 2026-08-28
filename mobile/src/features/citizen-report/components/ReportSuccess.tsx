import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';
import * as Clipboard from 'expo-clipboard';

import { useI18n } from '@/i18n/LocaleProvider';
import { CivicIllustration } from '@/components/CivicIllustration';
import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import type { SubmitTicketResponse } from '@/types/ticket';

type ReportSuccessProps = {
  result: SubmitTicketResponse;
  onReportAnother: () => void;
};

/**
 * Citizen-facing confirmation. Deliberately omits the internal `ticketId` (database key) —
 * only the ticket number and tracking code are ever shown to citizens.
 */
export function ReportSuccess({ result, onReportAnother }: ReportSuccessProps) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopyTrackingCode = async () => {
    try {
      await Clipboard.setStringAsync(result.trackingCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Clipboard is a convenience only — never block the confirmation on it.
    }
  };

  return (
    <View style={styles.container}>
      <CivicIllustration name="report-resolved" style={styles.successArtwork} />
      <Text variant="headlineSmall" style={styles.title}>
        {t('report.submitted')}
      </Text>
      <Text variant="bodyMedium" style={styles.message}>
        {result.message}
      </Text>

      <View style={styles.referenceBlock}>
        <Text variant="labelLarge" style={styles.referenceLabel}>
          {t('report.ticketNumber')}
        </Text>
        <Text variant="headlineMedium" style={styles.ticketNumber}>
          {result.ticketNumber}
        </Text>

        <Text variant="labelLarge" style={styles.referenceLabel}>
          {t('report.trackingCode')}
        </Text>
        <View style={styles.trackingRow}>
          <Text variant="titleLarge" style={styles.trackingCode}>
            {result.trackingCode}
          </Text>
          <Button
            mode="text"
            compact
            textColor={colors.brandDark}
            style={styles.copyButton}
            onPress={() => {
              void handleCopyTrackingCode();
            }}
          >
            {copied ? t('report.copied') : t('report.copy')}
          </Button>
        </View>

        <Text variant="bodySmall" style={styles.trackingHint}>
          {t('report.saveCodes')}
        </Text>
      </View>

      <View style={styles.actions}>
        <Link
          href={
            { pathname: '/track', params: { trackingCode: result.trackingCode } } as unknown as Href
          }
          asChild
        >
          <Button
            mode="contained"
            icon="magnify"
            style={styles.actionButton}
            contentStyle={styles.actionButtonContent}
            buttonColor={colors.brand}
            textColor={colors.textInverse}
          >
            {t('report.trackThis')}
          </Button>
        </Link>
        <Link href={'/' as Href} asChild>
          <Button
            mode="outlined"
            icon="home-outline"
            style={styles.actionButton}
            contentStyle={styles.actionButtonContent}
            textColor={colors.brandDark}
          >
            {t('report.backHome')}
          </Button>
        </Link>
      </View>

      <Button
        mode="text"
        onPress={onReportAnother}
        textColor={colors.textSecondary}
        style={styles.anotherButton}
      >
        {t('report.reportAnother')}
      </Button>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing[5],
    padding: spacing[5],
  },
  successArtwork: { width: 176, height: 146 },
  title: {
    fontWeight: '700',
    color: colors.text,
  },
  message: {
    color: colors.textSecondary,
  },
  referenceBlock: {
    gap: spacing[1],
    padding: spacing[4],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.brandSoft,
  },
  referenceLabel: {
    marginTop: spacing[2],
    color: colors.textSecondary,
    fontWeight: '700',
    fontSize: typography.label,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  ticketNumber: {
    color: colors.brandDark,
    fontWeight: '700',
  },
  trackingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  trackingCode: {
    color: colors.text,
    fontWeight: '700',
  },
  copyButton: {
    minHeight: touchTargetMin,
    justifyContent: 'center',
  },
  trackingHint: {
    marginTop: spacing[2],
    color: colors.textMuted,
  },
  actions: {
    gap: spacing[3],
  },
  actionButton: {
    borderRadius: radii.md,
  },
  actionButtonContent: {
    minHeight: touchTargetMin,
  },
  anotherButton: {
    alignSelf: 'center',
  },
});

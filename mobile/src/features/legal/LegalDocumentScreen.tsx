import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';
import { Banner, Button, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SimpleMarkdown } from '@/features/legal/SimpleMarkdown';
import { useI18n } from '@/i18n/LocaleProvider';
import { getLegalDocument } from '@/services/api/legal';
import { colors, radii, spacing } from '@/theme';
import type { LegalDocumentId } from '@/types/legal';

type LegalDocumentScreenProps = {
  documentId: LegalDocumentId;
  titleKey: string;
  showHubLinks?: boolean;
  showScopeNotice?: boolean;
};

export function LegalDocumentScreen({
  documentId,
  titleKey,
  showHubLinks = false,
  showScopeNotice = false,
}: LegalDocumentScreenProps) {
  const { t, locale } = useI18n();
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const doc = await getLegalDocument(documentId, locale);
      setMarkdown(doc.markdown);
      setVersion(doc.version);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('legal.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when locale/doc changes
  }, [documentId, locale]);

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text variant="headlineSmall" style={styles.title}>
          {t(titleKey)}
        </Text>

        {showScopeNotice ? (
          <View style={styles.scopeBox}>
            <Text variant="titleSmall" style={styles.section}>
              {t('privacy.scopeTitle')}
            </Text>
            <Text variant="bodyMedium" style={styles.paragraph}>
              {t('privacy.publicScope')}
            </Text>
            <Text variant="bodyMedium" style={styles.paragraph}>
              {t('privacy.internalRestriction')}
            </Text>
            <Text variant="bodyMedium" style={styles.paragraph}>
              {t('privacy.trackingScope')}
            </Text>
          </View>
        ) : null}

        {showHubLinks ? (
          <View style={styles.links}>
            <Link href={'/terms' as Href} asChild>
              <Button mode="text" textColor={colors.brandDark}>
                {t('legal.termsTitle')}
              </Button>
            </Link>
            <Link href={'/acceptable-use' as Href} asChild>
              <Button mode="text" textColor={colors.brandDark}>
                {t('legal.acceptableUseTitle')}
              </Button>
            </Link>
          </View>
        ) : null}

        {loading ? <ActivityIndicator color={colors.brand} /> : null}
        {error ? (
          <Banner visible icon="alert-circle" style={styles.banner}>
            {error}
          </Banner>
        ) : null}
        {error ? (
          <Button mode="outlined" onPress={() => void load()}>
            {t('common.retry')}
          </Button>
        ) : null}
        {!loading && !error && version ? (
          <Text variant="bodySmall" style={styles.version}>
            {t('legal.version', { version })}
          </Text>
        ) : null}
        {!loading && !error && markdown ? <SimpleMarkdown markdown={markdown} /> : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[5], gap: spacing[3], paddingBottom: spacing[8] },
  title: { fontWeight: '700', color: colors.brandDark },
  scopeBox: { gap: spacing[2], marginBottom: spacing[2] },
  section: { fontWeight: '600', color: colors.text },
  paragraph: { color: colors.textSecondary, lineHeight: 22 },
  links: { gap: spacing[1] },
  banner: { borderRadius: radii.md },
  version: { color: colors.textMuted },
});

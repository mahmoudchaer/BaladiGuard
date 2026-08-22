import { useEffect, useState } from 'react';
import { SimpleMarkdown } from '@/components/SimpleMarkdown';
import { useI18n } from '@/i18n/LocaleProvider';
import { getLegalDocument } from '@/services/legal';
import type { LegalDocumentId } from '@/types/legal';

type LegalDocumentPageProps = {
  documentId: LegalDocumentId;
  /** Optional i18n title override (privacy keeps "Privacy" for a11y/tests). */
  titleKey?: string;
  showPublicScope?: boolean;
};

export function LegalDocumentPage({
  documentId,
  titleKey,
  showPublicScope = false,
}: LegalDocumentPageProps) {
  const { t, locale } = useI18n();
  const [title, setTitle] = useState<string | null>(null);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const doc = await getLegalDocument(documentId, locale);
        if (cancelled) return;
        setTitle(doc.title);
        setMarkdown(doc.markdown);
        setVersion(doc.version);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t('legal.loadFailed'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId, locale, t]);

  const heading = titleKey ? t(titleKey) : (title ?? t('legal.loadingTitle'));

  return (
    <div className="page">
      <h1>{heading}</h1>
      {showPublicScope ? (
        <div className="panel stack" style={{ marginBottom: '1rem' }}>
          <p style={{ margin: 0, fontWeight: 600 }}>{t('privacy.scopeTitle')}</p>
          <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.publicScope')}</p>
          <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.internalRestriction')}</p>
          <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.trackingScope')}</p>
        </div>
      ) : null}
      {loading ? <p className="helper">{t('common.loading')}</p> : null}
      {error ? (
        <div className="notice notice-error" role="alert">
          {error}
        </div>
      ) : null}
      {!loading && !error && markdown ? (
        <div className="panel stack">
          {version ? (
            <p className="helper" style={{ margin: 0 }}>
              {t('legal.version', { version })}
            </p>
          ) : null}
          <SimpleMarkdown markdown={markdown} />
        </div>
      ) : null}
    </div>
  );
}

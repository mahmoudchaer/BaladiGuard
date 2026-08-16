import { useI18n } from '@/i18n/LocaleProvider';

export function PrivacyPage() {
  const { t } = useI18n();
  return (
    <div className="page">
      <h1>{t('privacy.title')}</h1>
      <div className="panel stack">
        <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.publicScope')}</p>
        <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.internalRestriction')}</p>
        <p style={{ margin: 0, lineHeight: 1.55 }}>{t('privacy.trackingScope')}</p>
      </div>
    </div>
  );
}

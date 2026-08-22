import { DashboardLayout } from '@/components/DashboardLayout';
import { useI18n } from '@/i18n/LocaleProvider';
import { config } from '@/services/config';
import './StaffLegalPage.css';

export function StaffLegalPage() {
  const { t } = useI18n();
  const citizenBase = config.citizenWebUrl?.replace(/\/+$/, '') ?? null;

  return (
    <DashboardLayout title={t('legal.title')} subtitle={t('legal.subtitle')}>
      <section className="staff-legal" aria-labelledby="staff-legal-title">
        <header className="staff-legal__header">
          <p className="staff-legal__eyebrow">{t('legal.eyebrow')}</p>
          <h2 id="staff-legal-title">{t('legal.title')}</h2>
          <p className="staff-legal__lede">{t('legal.lede')}</p>
        </header>

        <div className="staff-legal__card">
          <h3>{t('legal.dutiesTitle')}</h3>
          <ul>
            <li>{t('legal.dutyMinimize')}</li>
            <li>{t('legal.dutyNeedToKnow')}</li>
            <li>{t('legal.dutyNoExport')}</li>
            <li>{t('legal.dutyRedaction')}</li>
            <li>{t('legal.dutyRetention')}</li>
          </ul>
        </div>

        <div className="staff-legal__card">
          <h3>{t('legal.docsTitle')}</h3>
          <p>{t('legal.docsBody')}</p>
          {citizenBase ? (
            <ul className="staff-legal__links">
              <li>
                <a href={`${citizenBase}/privacy`} target="_blank" rel="noreferrer">
                  {t('legal.linkPrivacy')}
                </a>
              </li>
              <li>
                <a href={`${citizenBase}/terms`} target="_blank" rel="noreferrer">
                  {t('legal.linkTerms')}
                </a>
              </li>
              <li>
                <a href={`${citizenBase}/acceptable-use`} target="_blank" rel="noreferrer">
                  {t('legal.linkAcceptableUse')}
                </a>
              </li>
            </ul>
          ) : (
            <p className="staff-legal__note">{t('legal.citizenUrlMissing')}</p>
          )}
        </div>
      </section>
    </DashboardLayout>
  );
}

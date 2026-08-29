import { Link } from 'react-router-dom';
import { useI18n } from '@/i18n/LocaleProvider';

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <div className="page" data-testid="not-found-page">
      <h1>{t('notFound.title')}</h1>
      <div className="panel stack">
        <p style={{ margin: 0, lineHeight: 1.55 }}>{t('notFound.body')}</p>
        <Link className="button" to="/reports">
          {t('notFound.browse')}
        </Link>
        <Link to="/track">{t('notFound.track')}</Link>
      </div>
    </div>
  );
}

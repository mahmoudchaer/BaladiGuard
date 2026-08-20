import { translateStatus } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';

function statusTone(status: string): string {
  return status.toLowerCase().replaceAll('_', '-');
}

export function StatusChip({ status }: { status: string }) {
  const { t } = useI18n();
  const label = translateStatus(status);
  return (
    <span
      className={`status status-${statusTone(status)}`}
      aria-label={t('a11y.statusWithLabel', { status: label })}
    >
      {label}
    </span>
  );
}

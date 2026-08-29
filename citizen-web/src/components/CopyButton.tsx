import { useState } from 'react';
import { useI18n } from '@/i18n/LocaleProvider';

type CopyButtonProps = {
  value: string;
  label?: string;
};

export function CopyButton({ value, label }: CopyButtonProps) {
  const { t } = useI18n();
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setStatus('copied');
      window.setTimeout(() => setStatus('idle'), 2000);
    } catch {
      setStatus('failed');
    }
  }

  return (
    <span className="copy-control">
      <button type="button" className="text-button" onClick={() => void copy()}>
        {status === 'copied' ? t('common.copied') : (label ?? t('common.copy'))}
      </button>
      {status === 'failed' ? (
        <span className="copy-control__error" role="alert">
          {t('common.copyFailed')}
        </span>
      ) : null}
    </span>
  );
}

import { useState } from 'react';
import { useI18n } from '@/i18n/LocaleProvider';

type CopyButtonProps = {
  value: string;
  label?: string;
};

export function CopyButton({ value, label }: CopyButtonProps) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard can be unavailable in older browsers or insecure contexts.
    }
  }

  return (
    <button type="button" className="text-button" onClick={() => void copy()}>
      {copied ? t('common.copied') : (label ?? t('common.copy'))}
    </button>
  );
}

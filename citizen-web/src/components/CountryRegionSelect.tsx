import { useI18n } from '@/i18n/LocaleProvider';

const REGIONS = [
  { value: 'LB', labelKey: 'auth.lebanon' },
  { value: 'US', labelKey: 'auth.unitedStates' },
  { value: 'FR', labelKey: 'auth.france' },
  { value: 'GB', labelKey: 'auth.unitedKingdom' },
] as const;

type CountryRegionSelectProps = {
  id: string;
  value: string;
  onChange: (region: string) => void;
};

export function CountryRegionSelect({ id, value, onChange }: CountryRegionSelectProps) {
  const { t } = useI18n();
  return (
    <select
      id={id}
      className="input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {REGIONS.map((region) => (
        <option key={region.value} value={region.value}>
          {t(region.labelKey)}
        </option>
      ))}
    </select>
  );
}

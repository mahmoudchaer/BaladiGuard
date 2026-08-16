import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors, radii, spacing, touchTargetMin } from '@/theme';

export function LanguageSwitcher() {
  const { locale, t, setLocalePreference } = useI18n();

  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={t('a11y.languageGroup')}>
      <Text style={styles.heading}>{t('common.language')}</Text>
      <Text style={styles.hint}>{t('language.hint')}</Text>
      <View style={styles.row}>
        {SUPPORTED_LOCALES.map((option) => {
          const selected = option === locale;
          return (
            <Pressable
              key={option}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={t(`language.${option}`)}
              onPress={() => void setLocalePreference(option as AppLocale)}
              style={[styles.option, selected && styles.optionSelected]}
              testID={`language-option-${option}`}
            >
              <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>
                {t(`language.${option}`)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  heading: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing[1],
  },
  hint: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: spacing[3],
  },
  row: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing[2],
  },
  option: {
    minHeight: touchTargetMin,
    minWidth: touchTargetMin,
    paddingHorizontal: spacing[4],
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  optionSelected: {
    borderColor: colors.brandDark,
    backgroundColor: colors.brandSoft,
  },
  optionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  optionLabelSelected: {
    color: colors.brandDark,
  },
});

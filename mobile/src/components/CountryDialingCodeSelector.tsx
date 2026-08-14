import { useMemo, useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
} from 'react-native';
import { Button, Text, TextInput } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';
import {
  filterCountryDialingOptions,
  findCountryDialingOption,
  listCountryDialingOptions,
  type CountryDialingOption,
} from '@/utils/countryDialing';

export type CountryDialingCodeSelectorProps = {
  value: string;
  onChange: (region: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  error?: boolean;
  /** BCP 47 locale for country names; English names are the fallback. */
  locale?: string;
  testID?: string;
};

export function CountryDialingCodeSelector({
  value,
  onChange,
  onBlur,
  disabled = false,
  error = false,
  locale = 'en',
  testID = 'country-dialing-selector',
}: CountryDialingCodeSelectorProps) {
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const catalog = useMemo(() => listCountryDialingOptions(locale), [locale]);
  const selected =
    findCountryDialingOption(value, locale, catalog) ??
    findCountryDialingOption('LB', locale, catalog);
  const filtered = useMemo(() => filterCountryDialingOptions(catalog, query), [catalog, query]);

  const openMenu = () => {
    if (disabled) {
      return;
    }
    setQuery('');
    setOpen(true);
  };

  const closeMenu = () => {
    setOpen(false);
    setQuery('');
    onBlur?.();
  };

  const selectCountry = (option: CountryDialingOption) => {
    onChange(option.region);
    closeMenu();
  };

  const sheetMaxHeight = Math.max(
    320,
    Math.min(windowHeight * 0.72, windowHeight - insets.top - 48),
  );

  return (
    <View style={styles.wrap}>
      <Text variant="labelLarge" style={styles.fieldLabel} accessibilityRole="text">
        Country
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Country"
        accessibilityHint="Opens the list of countries and dialing codes"
        accessibilityState={{ disabled, expanded: open }}
        accessibilityValue={{ text: selected?.label ?? value }}
        disabled={disabled}
        onPress={openMenu}
        style={[
          styles.trigger,
          error ? styles.triggerError : null,
          disabled ? styles.triggerDisabled : null,
        ]}
        testID={testID}
      >
        <Text
          variant="bodyLarge"
          style={styles.triggerValue}
          numberOfLines={2}
          testID={`${testID}-value`}
        >
          {selected?.label ?? value}
        </Text>
        <Text style={styles.chevron} accessibilityElementsHidden>
          ▼
        </Text>
      </Pressable>

      <Modal
        visible={open}
        animationType="slide"
        transparent
        onRequestClose={closeMenu}
        testID={`${testID}-modal`}
      >
        <View style={styles.backdrop}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.keyboardAvoid}
          >
            <View
              style={[
                styles.sheet,
                {
                  maxHeight: sheetMaxHeight,
                  paddingBottom: Math.max(insets.bottom, spacing[3]),
                },
              ]}
              accessibilityViewIsModal
            >
              <Text variant="titleMedium" style={styles.sheetTitle} accessibilityRole="header">
                Select country
              </Text>
              <Text variant="bodySmall" style={styles.sheetSubtitle}>
                Search by country name, ISO code, or dialing code. Each country keeps its own ISO
                region even when dialing codes are shared.
              </Text>
              <TextInput
                mode="outlined"
                label="Search countries"
                placeholder="Lebanon, LB, or 961"
                value={query}
                onChangeText={setQuery}
                autoCapitalize="none"
                autoCorrect={false}
                outlineColor={colors.border}
                activeOutlineColor={colors.brand}
                style={styles.searchInput}
                testID={`${testID}-search`}
                accessibilityLabel="Search countries"
              />
              <FlatList
                data={filtered}
                keyExtractor={(item) => item.region}
                keyboardShouldPersistTaps="handled"
                style={[styles.list, { maxHeight: Math.max(160, sheetMaxHeight - 220) }]}
                contentContainerStyle={styles.listContent}
                testID={`${testID}-list`}
                ListEmptyComponent={
                  <Text style={styles.empty} testID={`${testID}-empty`}>
                    No countries match that search.
                  </Text>
                }
                renderItem={({ item }) => {
                  const isSelected = item.region === (selected?.region ?? value);
                  return (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={item.label}
                      accessibilityState={{ selected: isSelected }}
                      onPress={() => selectCountry(item)}
                      style={[styles.row, isSelected ? styles.rowSelected : null]}
                      testID={`${testID}-option-${item.region}`}
                    >
                      <Text style={styles.rowLabel} numberOfLines={2}>
                        {item.label}
                      </Text>
                      <Text style={styles.rowIso} accessibilityElementsHidden>
                        {item.region}
                      </Text>
                    </Pressable>
                  );
                }}
              />
              <Button
                mode="outlined"
                onPress={closeMenu}
                style={styles.closeButton}
                contentStyle={styles.closeContent}
                textColor={colors.textSecondary}
                testID={`${testID}-close`}
                accessibilityLabel="Close country list"
              >
                Close
              </Button>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexGrow: 1,
    flexShrink: 1,
    flexBasis: 148,
    minWidth: 132,
    gap: spacing[1],
  },
  fieldLabel: {
    color: colors.textSecondary,
    fontSize: typography.label,
    fontWeight: '600',
  },
  trigger: {
    minHeight: touchTargetMin,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing[3],
    paddingVertical: spacing[2],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[2],
  },
  triggerError: {
    borderColor: colors.danger,
  },
  triggerDisabled: {
    opacity: 0.55,
  },
  triggerValue: {
    flex: 1,
    color: colors.text,
    fontSize: typography.bodyCompact,
  },
  chevron: {
    color: colors.textMuted,
    fontSize: 10,
  },
  backdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(26, 35, 50, 0.45)',
  },
  keyboardAvoid: {
    width: '100%',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing[4],
    paddingTop: spacing[4],
    borderTopWidth: 1,
    borderColor: colors.border,
    gap: spacing[2],
  },
  sheetTitle: {
    fontWeight: '700',
    color: colors.text,
  },
  sheetSubtitle: {
    color: colors.textSecondary,
    marginBottom: spacing[1],
    lineHeight: 18,
  },
  searchInput: {
    backgroundColor: colors.surface,
  },
  list: {
    flexGrow: 0,
  },
  listContent: {
    paddingBottom: spacing[2],
  },
  row: {
    minHeight: touchTargetMin,
    paddingVertical: spacing[2],
    paddingHorizontal: spacing[2],
    borderRadius: radii.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing[2],
  },
  rowSelected: {
    backgroundColor: colors.brandSoft,
  },
  rowLabel: {
    flex: 1,
    color: colors.text,
    fontSize: typography.body,
  },
  rowIso: {
    color: colors.textMuted,
    fontSize: typography.metadata,
    fontWeight: '600',
  },
  empty: {
    color: colors.textSecondary,
    padding: spacing[4],
    textAlign: 'center',
  },
  closeButton: {
    marginTop: spacing[1],
    borderRadius: radii.md,
  },
  closeContent: {
    minHeight: touchTargetMin,
  },
});

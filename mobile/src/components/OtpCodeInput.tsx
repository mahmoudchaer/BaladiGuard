import { useEffect, useRef } from 'react';
import { Platform, Pressable, StyleSheet, TextInput as RNTextInput, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors, radii, spacing, touchTargetMin, typography } from '@/theme';

type OtpCodeInputProps = {
  value: string;
  onChangeText: (text: string) => void;
  onBlur?: () => void;
  length?: number;
  error?: boolean;
  disabled?: boolean;
  testID?: string;
};

/**
 * Segmented OTP entry: a single native TextInput (for paste/autofill support)
 * layered over decorative per-digit boxes.
 */
export function OtpCodeInput({
  value,
  onChangeText,
  onBlur,
  length = 6,
  error = false,
  disabled = false,
  testID,
}: OtpCodeInputProps) {
  const inputRef = useRef<RNTextInput>(null);
  const digits = Array.from({ length }, (_, index) => value[index] ?? '');

  useEffect(() => {
    if (disabled) {
      return;
    }
    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
    return () => clearTimeout(timer);
  }, [disabled]);

  return (
    <Pressable
      style={styles.wrapper}
      onPress={() => {
        if (!disabled) {
          inputRef.current?.focus();
        }
      }}
      accessibilityRole="none"
    >
      <View style={styles.boxRow} pointerEvents="none">
        {digits.map((digit, index) => {
          const isNextEmpty = index === value.length;
          return (
            <View
              key={index}
              style={[
                styles.box,
                isNextEmpty && !disabled ? styles.boxActive : null,
                error ? styles.boxError : null,
              ]}
            >
              <Text style={styles.boxText}>{digit}</Text>
            </View>
          );
        })}
      </View>
      <RNTextInput
        ref={inputRef}
        value={value}
        onChangeText={(text) => onChangeText(text.replace(/[^0-9]/g, '').slice(0, length))}
        onBlur={onBlur}
        keyboardType={Platform.OS === 'ios' ? 'number-pad' : 'numeric'}
        inputMode="numeric"
        maxLength={length}
        editable={!disabled}
        style={styles.hiddenInput}
        caretHidden
        showSoftInputOnFocus
        textContentType="oneTimeCode"
        autoComplete="sms-otp"
        importantForAutofill="yes"
        testID={testID}
        accessibilityLabel="Verification code"
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    position: 'relative',
  },
  boxRow: {
    flexDirection: 'row',
    gap: spacing[2],
  },
  box: {
    flex: 1,
    height: touchTargetMin,
    borderRadius: radii.md,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxActive: {
    borderColor: colors.brand,
  },
  boxError: {
    borderColor: colors.danger,
  },
  boxText: {
    fontSize: typography.pageTitle,
    fontWeight: '700',
    color: colors.text,
  },
  // Fully transparent inputs often fail to open the soft keyboard on Android.
  hiddenInput: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    opacity: 0.02,
    color: 'transparent',
    zIndex: 2,
  },
});

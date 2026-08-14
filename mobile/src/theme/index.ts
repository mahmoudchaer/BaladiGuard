import { MD3LightTheme } from 'react-native-paper';

/**
 * BaladiGuard Civic Command Desk tokens (citizen-facing, warmer density).
 * Conceptual parity with admin/src/index.css - platform-native values.
 */
export const colors = {
  brand: '#007A3D',
  brandDark: '#005C2E',
  brandSoft: '#E6F4EC',
  accent: '#CE1126',
  accentDark: '#A50E1F',
  accentSoft: '#FDE8EB',

  background: '#F2F2F7',
  surface: '#FFFFFF',
  surfaceSubtle: '#F7F7FA',
  border: '#E5E5EA',
  borderStrong: '#C7C7CC',

  text: '#111827',
  textSecondary: '#596273',
  textMuted: '#7C8492',
  textInverse: '#FFFFFF',

  success: '#007A3D',
  successSoft: '#E6F4EC',
  warning: '#B45309',
  warningSoft: '#FEF3E2',
  danger: '#CE1126',
  dangerSoft: '#FDE8EB',
  info: '#1D5A7A',
  infoSoft: '#E8F0F6',

  urgency: {
    low: { fg: '#4F5D6F', bg: '#EEF1F4' },
    medium: { fg: '#8F4A08', bg: '#FEF3E2' },
    high: { fg: '#A50E1F', bg: '#FDE8EB' },
    critical: { fg: '#6D121D', bg: '#FDE4E8' },
  },

  status: {
    SUBMITTED: { fg: '#1A4D6E', bg: '#E8F0F6' },
    UNDER_REVIEW: { fg: '#5B4510', bg: '#F7F0DF' },
    ASSIGNED: { fg: '#0E7490', bg: '#ECFEFF' },
    IN_PROGRESS: { fg: '#A50E1F', bg: '#FDE8EB' },
    RESOLVED: { fg: '#005C2E', bg: '#E6F4EC' },
    CLOSED: { fg: '#4A4A4A', bg: '#F0F0F0' },
  },
} as const;

export const spacing = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
} as const;

export const radii = {
  sm: 10,
  md: 14,
  lg: 20,
  xl: 28,
  pill: 999,
} as const;

export const shadows = {
  small: {
    shadowColor: '#0A1F16',
    shadowOpacity: 0.07,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
    elevation: 2,
  },
  medium: {
    shadowColor: '#0A1F16',
    shadowOpacity: 0.11,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 7 },
    elevation: 4,
  },
  large: {
    shadowColor: '#003D20',
    shadowOpacity: 0.18,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 7,
  },
} as const;

export const typography = {
  pageTitle: 28,
  sectionTitle: 18,
  body: 16,
  bodyCompact: 14,
  metadata: 12,
  label: 12,
  control: 16,
  helper: 13,
} as const;

/** Minimum comfortable tap target (approx. 44pt). */
export const touchTargetMin = 48;

export const theme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: colors.brand,
    secondary: colors.info,
    surface: colors.surface,
    background: colors.background,
    error: colors.danger,
    onPrimary: colors.textInverse,
    onSecondary: colors.textInverse,
    onSurface: colors.text,
    onBackground: colors.text,
    outline: colors.border,
  },
  roundness: radii.lg,
};

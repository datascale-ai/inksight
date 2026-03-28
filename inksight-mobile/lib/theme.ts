export const theme = {
  colors: {
    background: '#FFFFFF',
    card: '#FFFFFF',
    surface: '#F0F0F0',
    border: '#CCCCCC',
    ink: '#000000',
    brandInk: '#000000',
    secondary: '#555555',
    tertiary: '#888888',
    accent: '#000000',
    accentSoft: '#E8E8E8',
    hero: '#FFFFFF',
    heroBorder: '#000000',
    success: '#000000',
    danger: '#000000',
    shadow: 'rgba(0,0,0,0.12)',
  },
  spacing: {
    xs: 6,
    sm: 10,
    md: 16,
    lg: 20,
    xl: 28,
  },
  radius: {
    sm: 12,
    md: 16,
    lg: 22,
    xl: 28,
    pill: 999,
  },
  fonts: {
    sans: 'System',
    serif: 'Georgia',
  },
  strokeWidth: 1.8,
} as const;

export type InkTheme = typeof theme;

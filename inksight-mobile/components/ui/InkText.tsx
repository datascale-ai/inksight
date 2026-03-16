import { Text, type TextProps, StyleSheet } from 'react-native';
import { theme } from '@/lib/theme';

type Props = TextProps & {
  serif?: boolean;
  dimmed?: boolean;
};

export function InkText({ style, serif, dimmed, ...props }: Props) {
  return (
    <Text
      {...props}
      style={[
        styles.base,
        serif ? styles.serif : null,
        dimmed ? styles.dimmed : null,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    color: theme.colors.ink,
    fontFamily: theme.fonts.sans,
  },
  serif: {
    fontFamily: theme.fonts.serif,
  },
  dimmed: {
    color: theme.colors.secondary,
  },
});

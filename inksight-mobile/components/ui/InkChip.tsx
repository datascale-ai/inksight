import { Pressable, StyleSheet, type PressableProps, type ViewStyle } from 'react-native';
import { InkText } from '@/components/ui/InkText';
import { theme } from '@/lib/theme';

type Props = PressableProps & {
  label: string;
  active?: boolean;
};

export function InkChip({ label, active = false, style, ...props }: Props) {
  return (
    <Pressable
      {...props}
      style={({ pressed }) => [
        styles.base,
        active ? styles.active : null,
        pressed ? styles.pressed : null,
        style as ViewStyle,
      ]}
    >
      <InkText style={[styles.label, active ? styles.labelActive : null]}>{label}</InkText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: theme.radius.pill,
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  active: {
    backgroundColor: theme.colors.accentSoft,
    borderColor: theme.colors.heroBorder,
  },
  pressed: {
    opacity: 0.86,
  },
  label: {
    color: theme.colors.secondary,
    fontSize: 13,
    fontWeight: '600',
  },
  labelActive: {
    color: theme.colors.brandInk,
  },
});

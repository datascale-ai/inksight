import { StyleSheet, View } from 'react-native';
import type { LucideIcon } from 'lucide-react-native';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { theme } from '@/lib/theme';

type Props = {
  icon: LucideIcon;
  title: string;
  subtitle: string;
};

export function InkEmptyState({ icon: Icon, title, subtitle }: Props) {
  return (
    <InkCard style={styles.card}>
      <View style={styles.iconCircle}>
        <Icon size={28} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
      </View>
      <InkText style={styles.title}>{title}</InkText>
      <InkText dimmed style={styles.subtitle}>{subtitle}</InkText>
    </InkCard>
  );
}

const styles = StyleSheet.create({
  card: {
    alignItems: 'center',
    paddingVertical: theme.spacing.xl,
    gap: theme.spacing.sm,
  },
  iconCircle: {
    width: 64,
    height: 64,
    borderRadius: 999,
    backgroundColor: theme.colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing.sm,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  subtitle: {
    fontSize: 14,
    textAlign: 'center',
  },
});

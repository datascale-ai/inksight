import { Pressable, StyleSheet, View } from 'react-native';
import { Cpu, Wifi } from 'lucide-react-native';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { theme } from '@/lib/theme';

type Props = {
  title: string;
  subtitle: string;
  status: string;
  battery?: string;
  online?: boolean;
  onPress?: () => void;
};

export function DeviceCard({ title, subtitle, status, battery, online, onPress }: Props) {
  return (
    <Pressable onPress={onPress}>
      <InkCard>
        <View style={styles.header}>
          <View style={styles.identity}>
            <View style={styles.iconWrap}>
              <Cpu color={theme.colors.ink} size={18} strokeWidth={theme.strokeWidth} />
            </View>
            <View>
              <InkText style={styles.title}>{title}</InkText>
              <InkText dimmed style={styles.subtitle}>{subtitle}</InkText>
            </View>
          </View>
          <InkText style={styles.chevron}>›</InkText>
        </View>
        <View style={styles.metaRow}>
          <View style={styles.metaItem}>
            <Wifi color={online === false ? theme.colors.tertiary : theme.colors.success} size={14} strokeWidth={theme.strokeWidth} />
            <InkText dimmed>{status}</InkText>
          </View>
          {battery ? <InkText dimmed>{battery}</InkText> : null}
        </View>
      </InkCard>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconWrap: {
    width: 42,
    height: 42,
    borderRadius: theme.radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.surface,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
  },
  subtitle: {
    marginTop: 4,
  },
  chevron: {
    fontSize: 24,
    color: theme.colors.tertiary,
  },
  metaRow: {
    marginTop: theme.spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
});

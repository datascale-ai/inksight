import { StyleSheet, View } from 'react-native';
import { InkCard } from '@/components/ui/InkCard';
import { InkSkeleton } from '@/components/ui/InkSkeleton';
import { theme } from '@/lib/theme';

export function ContentCardSkeleton() {
  return (
    <InkCard>
      <View style={styles.header}>
        <InkSkeleton width={80} height={20} borderRadius={10} />
        <View style={styles.actions}>
          <InkSkeleton width={32} height={32} borderRadius={999} />
          <InkSkeleton width={32} height={32} borderRadius={999} />
        </View>
      </View>
      <InkSkeleton width="100%" height={200} borderRadius={theme.radius.md} style={styles.image} />
      <View style={styles.body}>
        <InkSkeleton width="100%" height={18} />
        <InkSkeleton width="70%" height={18} />
        <InkSkeleton width="40%" height={14} style={styles.attribution} />
      </View>
    </InkCard>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  image: {
    marginTop: theme.spacing.md,
  },
  body: {
    marginTop: theme.spacing.lg,
    gap: 10,
  },
  attribution: {
    marginTop: 4,
  },
});

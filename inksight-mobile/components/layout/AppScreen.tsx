import type { ReactNode } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ScrollView, StyleSheet, View, type ScrollViewProps } from 'react-native';
import { theme } from '@/lib/theme';

type Props = {
  scroll?: boolean;
  header?: ReactNode;
  contentContainerStyle?: ScrollViewProps['contentContainerStyle'];
  refreshControl?: ScrollViewProps['refreshControl'];
  children: ReactNode;
};

export function AppScreen({ scroll = true, header, children, contentContainerStyle, refreshControl }: Props) {
  const scrollStyle = header ? styles.scrollContentWithHeader : styles.scrollContent;
  const content = scroll ? (
    <ScrollView
      contentContainerStyle={[scrollStyle, contentContainerStyle]}
      showsVerticalScrollIndicator={false}
      refreshControl={refreshControl}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={scrollStyle}>{children}</View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      {header ? <View style={styles.header}>{header}</View> : null}
      {content}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  header: {
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.sm,
    paddingBottom: theme.spacing.md,
    backgroundColor: theme.colors.background,
  },
  scrollContent: {
    padding: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  scrollContentWithHeader: {
    paddingTop: theme.spacing.sm,
    paddingHorizontal: theme.spacing.lg,
    paddingBottom: theme.spacing.lg,
    gap: theme.spacing.md,
  },
});

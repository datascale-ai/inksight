import { ThemeProvider, DefaultTheme } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { QueryClientProvider } from '@tanstack/react-query';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useLayoutEffect } from 'react';
import { useFonts } from 'expo-font';
import { View } from 'react-native';
import 'react-native-reanimated';

import { I18nProvider, useI18n } from '@/lib/i18n';
import { useAuthStore } from '@/features/auth/store';
import { ensureLocalNotificationHandler } from '@/features/notifications/local';
import { queryClient } from '@/lib/query-client';
import { theme } from '@/lib/theme';
import { InkToastProvider } from '@/components/ui/InkToastProvider';
import { ErrorBoundary as CustomErrorBoundary } from '@/components/ErrorBoundary';

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from 'expo-router';

export const unstable_settings = {
  initialRouteName: '(tabs)',
};

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    SpaceMono: require('@/assets/fonts/SpaceMono-Regular.ttf'),
  });
  const bootstrap = useAuthStore((state) => state.bootstrap);

  // Defer until native Activity is attached — module-level preventAutoHideAsync()
  // can reject on Android Expo Go: "ExpoKeepAwake.activate ... activity is no longer available".
  useLayoutEffect(() => {
    void SplashScreen.preventAutoHideAsync().catch(() => undefined);
  }, []);

  useEffect(() => {
    bootstrap();
    ensureLocalNotificationHandler();
  }, [bootstrap]);

  if (!fontsLoaded) {
    return null;
  }

  return (
    <I18nProvider>
      <RootShell />
    </I18nProvider>
  );
}

function RootShell() {
  const { t, ready } = useI18n();

  useEffect(() => {
    if (ready) {
      void SplashScreen.hideAsync();
    }
  }, [ready]);

  if (!ready) {
    return <View style={{ flex: 1, backgroundColor: theme.colors.background }} />;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        value={{
          ...DefaultTheme,
          colors: {
            ...DefaultTheme.colors,
            background: theme.colors.background,
            card: theme.colors.card,
            primary: theme.colors.accent,
            text: theme.colors.ink,
            border: theme.colors.border,
          },
        }}>
        <CustomErrorBoundary>
          <InkToastProvider>
            <StatusBar style="dark" />
            <Stack screenOptions={{ contentStyle: { backgroundColor: theme.colors.background }, headerBackTitle: '', headerBackButtonDisplayMode: 'minimal' }}>
              <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
              <Stack.Screen name="onboarding" options={{ title: t('nav.welcome'), headerBackVisible: false }} />
              <Stack.Screen name="login" options={{ title: t('nav.login') }} />
              <Stack.Screen name="register" options={{ title: t('nav.register') }} />
              <Stack.Screen name="browse/modes" options={{ title: t('nav.modeCatalog') }} />
              <Stack.Screen name="browse/[id]" options={{ title: t('nav.detail') }} />
              <Stack.Screen name="create/generate" options={{ title: t('nav.aiGenerate') }} />
              <Stack.Screen name="device/[mac]" options={{ title: t('nav.deviceDetail') }} />
              <Stack.Screen name="device/[mac]/config" options={{ title: t('nav.deviceConfig') }} />
              <Stack.Screen name="device/[mac]/members" options={{ title: t('nav.deviceMembers') }} />
              <Stack.Screen name="device/[mac]/firmware" options={{ title: t('nav.firmware') }} />
              <Stack.Screen name="device/[mac]/mode-settings" options={{ title: t('device.modeSettings') }} />
              <Stack.Screen name="device/provision" options={{ title: t('nav.provision') }} />
              <Stack.Screen name="device/requests" options={{ title: t('nav.requests') }} />
            </Stack>
          </InkToastProvider>
        </CustomErrorBoundary>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

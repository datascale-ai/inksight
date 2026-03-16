import { Tabs } from 'expo-router';
import { Compass, Cpu, House, PenSquare, UserRound } from 'lucide-react-native';
import { Pressable, StyleSheet, View } from 'react-native';
import { theme } from '@/lib/theme';
import { InkText } from '@/components/ui/InkText';
import { useI18n } from '@/lib/i18n';

type TabConfig = {
  name: string;
  titleKey: string;
  icon: typeof House;
  center?: boolean;
};

const tabs: TabConfig[] = [
  { name: 'today/index', titleKey: 'tab.today', icon: House },
  { name: 'browse/index', titleKey: 'tab.browse', icon: Compass },
  { name: 'create/index', titleKey: 'tab.create', icon: PenSquare, center: true },
  { name: 'device/index', titleKey: 'tab.device', icon: Cpu },
  { name: 'me/index', titleKey: 'tab.me', icon: UserRound },
];

export default function TabLayout() {
  const { t } = useI18n();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.bar,
        tabBarShowLabel: false,
      }}>
      {tabs.map(({ name, titleKey, icon: Icon, center }) => {
        const title = t(titleKey);
        return (
          <Tabs.Screen
            key={name}
            name={name}
            options={{
              title,
              tabBarIcon: ({ focused }) => (
                <View style={center ? styles.centerWrap : styles.iconWrap}>
                  <View style={center ? styles.centerButton : undefined}>
                    <Icon
                      color={focused ? (center ? '#FFFFFF' : theme.colors.ink) : theme.colors.secondary}
                      size={center ? 22 : 20}
                      strokeWidth={theme.strokeWidth}
                    />
                  </View>
                  <InkText serif style={[styles.label, focused ? styles.labelActive : styles.labelInactive]}>
                    {title}
                  </InkText>
                </View>
              ),
              tabBarButton: (props) => (
                <Pressable
                  onPress={props.onPress}
                  onLongPress={props.onLongPress}
                  accessibilityState={props.accessibilityState}
                  accessibilityLabel={props.accessibilityLabel}
                  testID={props.testID}
                  style={[props.style, center ? styles.centerTabButton : styles.tabButton]}
                >
                  {props.children}
                </Pressable>
              ),
            }}
          />
        );
      })}
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: 72,
    paddingTop: 4,
    backgroundColor: 'rgba(250, 250, 248, 0.96)',
    borderTopColor: theme.colors.border,
  },
  tabButton: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerTabButton: {
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -18,
  },
  iconWrap: {
    alignItems: 'center',
    gap: 4,
  },
  centerWrap: {
    alignItems: 'center',
    gap: 4,
  },
  centerButton: {
    width: 52,
    height: 52,
    borderRadius: 999,
    backgroundColor: theme.colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  label: {
    fontSize: 11,
  },
  labelActive: {
    color: theme.colors.ink,
  },
  labelInactive: {
    color: theme.colors.secondary,
  },
});

import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Tabs, useRouter, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { colors } from '@/theme';

export default function CitizenTabsLayout() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useCitizenAuth();
  const showTabs = !isLoading && isAuthenticated;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.brandDark,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: styles.label,
        tabBarItemStyle: styles.item,
        tabBarHideOnKeyboard: true,
        tabBarStyle: showTabs ? styles.bar : styles.hiddenBar,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarAccessibilityLabel: 'Home',
          tabBarIcon: ({ color }) => <Icon source="home-outline" size={23} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'My Reports',
          tabBarAccessibilityLabel: 'My Reports',
          tabBarIcon: ({ color }) => (
            <Icon source="text-box-outline" size={23} color={String(color)} />
          ),
        }}
      />
      <Tabs.Screen
        name="report-action"
        options={{
          title: 'Report',
          tabBarAccessibilityLabel: 'Report',
          tabBarButton: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Report"
              accessibilityHint="Opens the new report form"
              onPress={() => router.push('/report' as Href)}
              style={({ pressed }) => [styles.reportButton, pressed && styles.reportPressed]}
            >
              <View style={styles.reportIcon}>
                <Icon source="plus" size={18} color={colors.textInverse} />
              </View>
              <Text style={styles.reportLabel}>Report</Text>
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: 'Explore',
          tabBarAccessibilityLabel: 'Explore',
          tabBarIcon: ({ color }) => <Icon source="map-outline" size={23} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: 'More',
          tabBarAccessibilityLabel: 'More',
          tabBarIcon: ({ color }) => (
            <Icon source="dots-horizontal" size={23} color={String(color)} />
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: {
    height: Platform.OS === 'ios' ? 84 : 68,
    paddingTop: 7,
    backgroundColor: 'rgba(250,250,252,0.96)',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(60,60,67,0.16)',
    shadowColor: '#000000',
    shadowOpacity: 0.04,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: -4 },
    elevation: 8,
  },
  hiddenBar: { display: 'none' },
  item: { paddingVertical: 1 },
  label: { fontSize: 10, fontWeight: '600', letterSpacing: -0.1 },
  reportButton: { flex: 1, alignItems: 'center', paddingTop: 5, gap: 3 },
  reportPressed: { opacity: 0.62 },
  reportIcon: {
    width: 28,
    height: 28,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.brand,
  },
  reportLabel: { fontSize: 10, fontWeight: '600', color: colors.brandDark },
});

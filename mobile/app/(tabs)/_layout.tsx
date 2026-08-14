import { Pressable, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Tabs, useRouter, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { colors, spacing, touchTargetMin } from '@/theme';

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
            <Icon source="clipboard-text-clock-outline" size={23} color={String(color)} />
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
              style={styles.reportButton}
            >
              <View style={styles.reportIcon}>
                <Icon source="plus" size={25} color={colors.textInverse} />
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
          tabBarIcon: ({ color }) => (
            <Icon source="map-search-outline" size={23} color={String(color)} />
          ),
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
    minHeight: 66,
    paddingTop: spacing[1],
    backgroundColor: colors.surface,
    borderTopColor: colors.border,
  },
  hiddenBar: { display: 'none' },
  label: { fontSize: 10, fontWeight: '600' },
  reportButton: {
    flex: 1,
    minHeight: 62,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 2,
  },
  reportIcon: {
    width: touchTargetMin,
    height: touchTargetMin,
    marginTop: -18,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: touchTargetMin / 2,
    backgroundColor: colors.brand,
    borderWidth: 4,
    borderColor: colors.surface,
  },
  reportLabel: { fontSize: 10, fontWeight: '700', color: colors.brandDark },
});

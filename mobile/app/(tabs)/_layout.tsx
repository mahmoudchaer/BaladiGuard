import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { Tabs, useRouter, type Href } from 'expo-router';

import { useCitizenAuth } from '@/auth';
import { useI18n } from '@/i18n/LocaleProvider';
import { colors } from '@/theme';

export default function CitizenTabsLayout() {
  const router = useRouter();
  const { t } = useI18n();
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
          title: t('tabs.home'),
          tabBarAccessibilityLabel: t('tabs.home'),
          tabBarIcon: ({ color }) => <Icon source="home-outline" size={23} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: t('tabs.history'),
          tabBarAccessibilityLabel: t('tabs.history'),
          tabBarIcon: ({ color }) => (
            <Icon source="text-box-outline" size={23} color={String(color)} />
          ),
        }}
      />
      <Tabs.Screen
        name="report-action"
        options={{
          title: t('tabs.report'),
          tabBarAccessibilityLabel: t('tabs.report'),
          tabBarButton: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('tabs.report')}
              accessibilityHint={t('tabs.reportHint')}
              onPress={() => router.push('/report' as Href)}
              style={({ pressed }) => [styles.reportButton, pressed && styles.reportPressed]}
            >
              <View style={styles.reportIcon}>
                <Icon source="plus" size={18} color={colors.textInverse} />
              </View>
              <Text style={styles.reportLabel}>{t('tabs.report')}</Text>
            </Pressable>
          ),
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: t('tabs.explore'),
          tabBarAccessibilityLabel: t('tabs.explore'),
          tabBarIcon: ({ color }) => <Icon source="map-outline" size={23} color={String(color)} />,
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: t('tabs.more'),
          tabBarAccessibilityLabel: t('tabs.more'),
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

import { Pressable, StyleSheet, View } from 'react-native';
import { Icon, Text } from 'react-native-paper';
import { useRouter, type Href } from 'expo-router';

import { colors, spacing, touchTargetMin } from '@/theme';

type Destination = 'home' | 'history' | 'report' | 'explore' | 'more';
const items: { key: Destination; label: string; icon: string; href: string }[] = [
  { key: 'home', label: 'Home', icon: 'home-outline', href: '/' },
  { key: 'history', label: 'My Reports', icon: 'clipboard-text-clock-outline', href: '/history' },
  { key: 'report', label: 'Report', icon: 'plus', href: '/report' },
  { key: 'explore', label: 'Explore', icon: 'map-search-outline', href: '/explore' },
  { key: 'more', label: 'More', icon: 'dots-horizontal', href: '/more' },
];

export function AppBottomNavigation({ active }: { active: Destination }) {
  const router = useRouter();
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {items.map((item) => {
        const selected = active === item.key;
        const emphasized = item.key === 'report';
        return (
          <Pressable
            key={item.key}
            onPress={() => router.replace(item.href as Href)}
            style={styles.item}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            accessibilityLabel={item.label}
          >
            <View
              style={[
                styles.icon,
                emphasized && styles.reportIcon,
                selected && !emphasized && styles.selectedIcon,
              ]}
            >
              <Icon
                source={item.icon}
                size={emphasized ? 25 : 23}
                color={
                  emphasized ? colors.textInverse : selected ? colors.brandDark : colors.textMuted
                }
              />
            </View>
            <Text style={[styles.label, selected && styles.selectedLabel]} numberOfLines={1}>
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing[1],
    paddingHorizontal: spacing[1],
  },
  item: { flex: 1, minHeight: 62, alignItems: 'center', justifyContent: 'center', gap: 2 },
  icon: { width: 38, height: 30, alignItems: 'center', justifyContent: 'center', borderRadius: 18 },
  selectedIcon: { backgroundColor: colors.brandSoft },
  reportIcon: {
    width: touchTargetMin,
    height: touchTargetMin,
    marginTop: -18,
    borderRadius: 24,
    backgroundColor: colors.brand,
    borderWidth: 4,
    borderColor: colors.surface,
  },
  label: { fontSize: 10, color: colors.textMuted },
  selectedLabel: { color: colors.brandDark, fontWeight: '700' },
});

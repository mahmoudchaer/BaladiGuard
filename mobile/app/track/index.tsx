import { StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { TrackLookupForm } from '@/features/ticket-tracking/TrackLookupForm';
import { colors } from '@/theme';

export default function TrackScreen() {
  const { trackingCode } = useLocalSearchParams<{ trackingCode?: string | string[] }>();
  const initialTrackingCode = Array.isArray(trackingCode) ? trackingCode[0] : trackingCode;

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <TrackLookupForm initialTrackingCode={initialTrackingCode} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
});

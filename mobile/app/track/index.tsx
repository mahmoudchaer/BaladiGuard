import { StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { TrackLookupForm } from '@/features/ticket-tracking/TrackLookupForm';

export default function TrackScreen() {
  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <TrackLookupForm />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
});

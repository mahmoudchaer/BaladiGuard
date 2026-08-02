import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { RequireContributionReady } from '@/auth/RequireContributionReady';
import { ReportForm } from '@/features/citizen-report/ReportForm';

export default function ReportScreen() {
  return (
    <RequireContributionReady returnTo="/report">
      <SafeAreaView style={styles.safeArea} edges={['bottom', 'left', 'right']}>
        <View style={styles.container}>
          <ReportForm />
        </View>
      </SafeAreaView>
    </RequireContributionReady>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  container: {
    flex: 1,
  },
});

import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function HomeScreen() {
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.container}>
        <Text variant="headlineLarge" style={styles.title}>
          BaladiGuard
        </Text>
        <Text variant="bodyLarge" style={styles.subtitle}>
          Report infrastructure issues in your municipality and track progress from your phone.
        </Text>
        <Link href="/report" asChild>
          <Button mode="contained" icon="clipboard-text-outline" style={styles.button}>
            Report an issue
          </Button>
        </Link>
        <Link href={'/track' as Href} asChild>
          <Button mode="outlined" icon="magnify" style={styles.button}>
            Track a report
          </Button>
        </Link>
        <Link href={'/privacy' as Href} asChild>
          <Button mode="text" style={styles.button}>
            Privacy notice
          </Button>
        </Link>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  container: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    gap: 16,
  },
  title: {
    fontWeight: '700',
    color: '#0B5FFF',
  },
  subtitle: {
    color: '#475569',
    marginBottom: 8,
  },
  button: {
    alignSelf: 'flex-start',
  },
});

import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { ActivityIndicator, Banner, Button, Card, Text } from 'react-native-paper';
import { Link, type Href } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useCitizenAuth } from '@/auth';
import { buildLoginHref } from '@/auth/returnTo';
import { getPublicTickets } from '@/services/api/tickets';
import type { PublicTicketResponse } from '@/types/ticket';

const categoryLabels: Record<string, string> = {
  road_damage: 'Road Damage',
  waste: 'Waste',
  street_lighting: 'Street Lighting',
  water_leak: 'Water Leak',
  noise: 'Noise',
  sidewalk_damage: 'Sidewalk Damage',
  traffic_signal: 'Traffic Signal',
  drainage: 'Drainage',
  public_facilities: 'Public Facilities',
};

const statusLabels: Record<PublicTicketResponse['status'], string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  IN_PROGRESS: 'In Progress',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

export default function HomeScreen() {
  const { isAuthenticated, contributionReady, profile, logout, isLoading } = useCitizenAuth();
  const [reports, setReports] = useState<PublicTicketResponse[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadReports() {
      setIsLoadingReports(true);
      setReportError(null);
      try {
        const response = await getPublicTickets({ limit: 20 });
        if (active) {
          setReports(response.items);
        }
      } catch (error) {
        if (active) {
          setReportError(
            error instanceof Error ? error.message : 'Unable to load public reports right now.',
          );
        }
      } finally {
        if (active) {
          setIsLoadingReports(false);
        }
      }
    }

    void loadReports();
    return () => {
      active = false;
    };
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text variant="headlineLarge" style={styles.title}>
          BaladiGuard
        </Text>
        <Text variant="bodyLarge" style={styles.subtitle}>
          Browse public infrastructure reports and contribute with a verified phone account.
        </Text>

        <View style={styles.actionRow}>
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
        </View>

        {!isLoading && isAuthenticated ? (
          <View style={styles.sessionBlock}>
            <Text variant="bodyMedium" style={styles.sessionText}>
              {`Signed in as ${profile?.fullName ?? profile?.phone}${
                !contributionReady ? ' - Finish setup in Profile' : ''
              }`}
            </Text>
            <Link href={'/profile' as Href} asChild>
              <Button
                mode="text"
                icon="account"
                style={styles.button}
                testID="profile-entry-button"
              >
                Profile
              </Button>
            </Link>
            <Link href={'/history' as Href} asChild>
              <Button
                mode="text"
                icon="history"
                style={styles.button}
                testID="history-entry-button"
              >
                My reports
              </Button>
            </Link>
            <Button
              mode="text"
              onPress={() => void logout()}
              style={styles.button}
              testID="logout-button"
            >
              Sign out
            </Button>
          </View>
        ) : (
          <View style={styles.guestActions}>
            <Link href={buildLoginHref('/') as Href} asChild>
              <Button
                mode="text"
                icon="cellphone-message"
                style={styles.button}
                testID="sign-in-button"
              >
                Sign in with phone
              </Button>
            </Link>
            <Link href={'/privacy' as Href} asChild>
              <Button mode="text" style={styles.button}>
                Privacy notice
              </Button>
            </Link>
          </View>
        )}

        <View style={styles.feedHeader}>
          <Text variant="titleLarge" style={styles.sectionTitle}>
            Public reports
          </Text>
          <Text variant="bodyMedium" style={styles.feedHint}>
            Public cards hide contact details, tracking codes, and exact coordinates.
          </Text>
        </View>

        {reportError ? (
          <Banner visible icon="alert-circle" style={styles.errorBanner}>
            {reportError}
          </Banner>
        ) : null}

        {isLoadingReports ? (
          <View style={styles.reportLoading} testID="public-reports-loading">
            <ActivityIndicator />
            <Text variant="bodyMedium">Loading public reports...</Text>
          </View>
        ) : (
          <View style={styles.publicContent} testID="public-report-feed">
            {reports.length > 0 ? (
              <MapView
                style={styles.map}
                initialRegion={{
                  latitude: reports[0].mapLocation.latitude,
                  longitude: reports[0].mapLocation.longitude,
                  latitudeDelta: 0.04,
                  longitudeDelta: 0.04,
                }}
              >
                {reports.map((report) => (
                  <Marker
                    key={report.ticketNumber}
                    coordinate={{
                      latitude: report.mapLocation.latitude,
                      longitude: report.mapLocation.longitude,
                    }}
                    title={report.ticketNumber}
                    description={report.location.addressText}
                  />
                ))}
              </MapView>
            ) : null}

            {reports.map((report) => (
              <Card key={report.ticketNumber} style={styles.reportCard}>
                <Card.Content style={styles.reportCardContent}>
                  <View style={styles.reportCardHeader}>
                    <Text variant="titleMedium" style={styles.reportNumber}>
                      {report.ticketNumber}
                    </Text>
                    <Text variant="labelMedium" style={styles.statusPill}>
                      {statusLabels[report.status]}
                    </Text>
                  </View>
                  <Text variant="bodyMedium">{report.description}</Text>
                  <Text variant="bodySmall" style={styles.metaText}>
                    {report.category
                      ? (categoryLabels[report.category] ?? report.category)
                      : 'Category pending'}{' '}
                    - {report.location.addressText}
                  </Text>
                  <Text variant="bodySmall" style={styles.metaText}>
                    Reported by {report.attribution.displayName}
                  </Text>
                </Card.Content>
              </Card>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  container: {
    padding: 24,
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
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  sessionBlock: {
    marginTop: 8,
    gap: 4,
  },
  sessionText: {
    color: '#334155',
  },
  guestActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  feedHeader: {
    gap: 4,
    marginTop: 12,
  },
  sectionTitle: {
    fontWeight: '700',
  },
  feedHint: {
    color: '#64748B',
  },
  errorBanner: {
    backgroundColor: '#FEF2F2',
  },
  reportLoading: {
    minHeight: 120,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  publicContent: {
    gap: 12,
  },
  map: {
    height: 220,
    borderRadius: 8,
  },
  reportCard: {
    borderRadius: 8,
  },
  reportCardContent: {
    gap: 8,
  },
  reportCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  reportNumber: {
    color: '#0B5FFF',
    fontWeight: '700',
  },
  statusPill: {
    color: '#166534',
  },
  metaText: {
    color: '#64748B',
  },
});

import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import MapView, { Marker } from 'react-native-maps';
import { ActivityIndicator, Banner, Card, Text } from 'react-native-paper';
import { useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { getPublicTicketByNumber } from '@/services/api/tickets';
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

export default function PublicReportDetailScreen() {
  const { ticketNumber } = useLocalSearchParams<{ ticketNumber?: string | string[] }>();
  const selectedTicketNumber = Array.isArray(ticketNumber) ? ticketNumber[0] : ticketNumber;
  const [report, setReport] = useState<PublicTicketResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadReport() {
      if (!selectedTicketNumber) {
        setError('Unable to open that public report.');
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const response = await getPublicTicketByNumber(selectedTicketNumber);
        if (active) {
          setReport(response);
        }
      } catch (loadError) {
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'Unable to load that public report right now.',
          );
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    void loadReport();
    return () => {
      active = false;
    };
  }, [selectedTicketNumber]);

  return (
    <SafeAreaView style={styles.safeArea} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.container}>
        {isLoading ? (
          <View style={styles.loading} testID="public-report-detail-loading">
            <ActivityIndicator />
            <Text variant="bodyMedium">Loading public report...</Text>
          </View>
        ) : null}

        {error ? (
          <Banner visible icon="alert-circle" style={styles.errorBanner}>
            {error}
          </Banner>
        ) : null}

        {report ? (
          <View style={styles.content} testID="public-report-detail">
            <View style={styles.header}>
              <Text variant="headlineSmall" style={styles.ticketNumber}>
                {report.ticketNumber}
              </Text>
              <Text variant="labelLarge" style={styles.statusPill}>
                {statusLabels[report.status]}
              </Text>
            </View>

            <MapView
              style={styles.map}
              initialRegion={{
                latitude: report.mapLocation.latitude,
                longitude: report.mapLocation.longitude,
                latitudeDelta: 0.025,
                longitudeDelta: 0.025,
              }}
            >
              <Marker
                coordinate={{
                  latitude: report.mapLocation.latitude,
                  longitude: report.mapLocation.longitude,
                }}
                title={report.ticketNumber}
                description={report.mapLocation.addressText}
              />
            </MapView>

            <Card style={styles.card}>
              <Card.Content style={styles.cardContent}>
                <Text variant="titleMedium">Summary</Text>
                <Text variant="bodyMedium">{report.description}</Text>
                <Text variant="bodySmall" style={styles.metaText}>
                  {report.category
                    ? (categoryLabels[report.category] ?? report.category)
                    : 'Category pending'}{' '}
                  - {report.location.addressText}
                </Text>
                {report.department ? (
                  <Text variant="bodySmall" style={styles.metaText}>
                    Assigned to {report.department.name}
                  </Text>
                ) : null}
                <Text variant="bodySmall" style={styles.metaText}>
                  Reported by {report.attribution.displayName}
                </Text>
              </Card.Content>
            </Card>
          </View>
        ) : null}
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
  loading: {
    minHeight: 160,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
  },
  errorBanner: {
    backgroundColor: '#FEF2F2',
  },
  content: {
    gap: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  ticketNumber: {
    color: '#0B5FFF',
    fontWeight: '700',
  },
  statusPill: {
    color: '#166534',
  },
  map: {
    height: 240,
    borderRadius: 8,
  },
  card: {
    borderRadius: 8,
  },
  cardContent: {
    gap: 8,
  },
  metaText: {
    color: '#64748B',
  },
});

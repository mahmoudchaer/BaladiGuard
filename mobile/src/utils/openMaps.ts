import { Linking, Platform } from 'react-native';

type MapTarget = {
  latitude: number;
  longitude: number;
  label?: string;
};

/** Open coordinates in Apple Maps (iOS) or Google Maps / geo intent (Android). */
export async function openInMapsApp(target: MapTarget): Promise<void> {
  const { latitude, longitude, label } = target;
  const encodedLabel = encodeURIComponent(label?.trim() || 'Report location');
  const coord = `${latitude},${longitude}`;

  const candidates =
    Platform.OS === 'ios'
      ? [
          `maps:0,0?q=${encodedLabel}@${coord}`,
          `http://maps.apple.com/?ll=${coord}&q=${encodedLabel}`,
        ]
      : [
          `geo:${coord}?q=${coord}(${encodedLabel})`,
          `https://www.google.com/maps/search/?api=1&query=${coord}`,
        ];

  for (const url of candidates) {
    try {
      const supported = await Linking.canOpenURL(url);
      if (supported) {
        await Linking.openURL(url);
        return;
      }
    } catch {
      // try next candidate
    }
  }

  await Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${coord}`);
}

import {
  Image,
  StyleSheet,
  type ImageSourcePropType,
  type ImageStyle,
  type StyleProp,
} from 'react-native';

export type CivicIllustrationName =
  | 'citizen-reporting'
  | 'municipal-worker'
  | 'lebanon-service-map'
  | 'report-clipboard'
  | 'report-resolved'
  | 'cedar-location'
  | 'community-contribution'
  | 'privacy-verified'
  | 'search-empty';

const isTest = process.env.NODE_ENV === 'test';

const sources: Record<CivicIllustrationName, ImageSourcePropType> = {
  'citizen-reporting': isTest
    ? { uri: 'citizen-reporting' }
    : require('../../assets/illustrations/citizen-reporting.png'),
  'municipal-worker': isTest
    ? { uri: 'municipal-worker' }
    : require('../../assets/illustrations/municipal-worker.png'),
  'lebanon-service-map': isTest
    ? { uri: 'lebanon-service-map' }
    : require('../../assets/illustrations/lebanon-service-map.png'),
  'report-clipboard': isTest
    ? { uri: 'report-clipboard' }
    : require('../../assets/illustrations/report-clipboard.png'),
  'report-resolved': isTest
    ? { uri: 'report-resolved' }
    : require('../../assets/illustrations/report-resolved.png'),
  'cedar-location': isTest
    ? { uri: 'cedar-location' }
    : require('../../assets/illustrations/cedar-location.png'),
  'community-contribution': isTest
    ? { uri: 'community-contribution' }
    : require('../../assets/illustrations/community-contribution.png'),
  'privacy-verified': isTest
    ? { uri: 'privacy-verified' }
    : require('../../assets/illustrations/privacy-verified.png'),
  'search-empty': isTest
    ? { uri: 'search-empty' }
    : require('../../assets/illustrations/search-empty.png'),
};

export function CivicIllustration({
  name,
  style,
  testID,
}: {
  name: CivicIllustrationName;
  style?: StyleProp<ImageStyle>;
  testID?: string;
}) {
  return (
    <Image
      source={sources[name]}
      resizeMode="contain"
      accessible={false}
      importantForAccessibility="no"
      style={[styles.base, style]}
      testID={testID}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    width: 160,
    height: 140,
    alignSelf: 'center',
  },
});

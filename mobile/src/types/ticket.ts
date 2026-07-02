export type LocationSource = 'GPS' | 'MANUAL' | 'PLACEHOLDER';

export type ReportLocation = {
  latitude: number;
  longitude: number;
  addressText: string;
  source: LocationSource;
};

export type ReportContact = {
  name?: string;
  phone?: string;
  email?: string;
  preferredChannel?: 'SMS' | 'EMAIL';
};

export type SubmitTicketRequest = {
  description: string;
  languageHint: 'auto' | string;
  contact: ReportContact;
  location: ReportLocation;
  imageObjectKey: string;
  clientMetadata: {
    platform: string;
    appVersion: string;
  };
};

export type SubmitTicketResponse = {
  ticketId: string;
  ticketNumber: string;
  trackingCode: string;
  status: 'SUBMITTED';
  message: string;
  createdAt: string;
};

export type ReportPhoto = {
  uri: string;
  fileName: string;
  contentType: string;
  sizeBytes?: number;
};

export type PlaceholderLocation = {
  id: string;
  label: string;
  addressText: string;
  latitude: number;
  longitude: number;
};

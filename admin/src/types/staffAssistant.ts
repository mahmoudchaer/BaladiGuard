export type StaffAssistantIntent =
  'high_priority_summary' | 'repeated_area_summary' | 'unsupported';

export type StaffAssistantTicketReference = {
  ticketId: string;
  ticketNumber: string;
  status: string;
  category: string;
  priority: string | null;
  slaState: string | null;
  municipalityId: string | null;
  departmentId: string | null;
  cellId: string | null;
  duplicateGroupId: string | null;
};

export type StaffAssistantAreaCluster = {
  cellId: string;
  south: number | null;
  west: number | null;
  north: number | null;
  east: number | null;
  label: string;
  ticketCount: number;
  distinctReportCount: number;
  duplicateGroupCount: number;
  separateReportCount: number;
  categories: Record<string, number>;
  ticketIds: string[];
  ticketIdsTruncated: boolean;
};

export type StaffAssistantResponse = {
  intent: StaffAssistantIntent;
  asOf: string;
  message: string;
  count: number;
  categories: Record<string, number>;
  statuses: Record<string, number>;
  departments: Record<string, number>;
  areas: Record<string, number>;
  areaClusters: StaffAssistantAreaCluster[];
  areaClusterTotal: number;
  areaClustersTruncated: boolean;
  unlocatedCount: number;
  incompleteCount: number;
  tickets: StaffAssistantTicketReference[];
  appliedFilters: Record<string, string>;
};

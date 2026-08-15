export type StaffSearchTicketHit = {
  resultType: 'ticket';
  ticketId: string;
  ticketNumber: string;
  trackingCode: string | null;
  status: string;
  category: string;
  publicLocationLabel: string | null;
};

export type StaffSearchWorkerHit = {
  resultType: 'worker';
  workerId: string;
  displayName: string;
  departmentIds: string[];
  active: boolean;
};

export type StaffSearchTeamHit = {
  resultType: 'team';
  teamId: string;
  displayName: string;
  departmentIds: string[];
  active: boolean;
};

export type StaffSearchWorkOrderHit = {
  resultType: 'work_order';
  workOrderId: string;
  ticketId: string;
  ticketNumber: string | null;
  state: string;
  summary: string;
};

export type StaffSearchResponse = {
  asOf: string;
  query: string;
  tickets: StaffSearchTicketHit[];
  workers: StaffSearchWorkerHit[];
  teams: StaffSearchTeamHit[];
  workOrders: StaffSearchWorkOrderHit[];
  ticketsTruncated: boolean;
  workersTruncated: boolean;
  teamsTruncated: boolean;
  workOrdersTruncated: boolean;
  scanTruncated: boolean;
  workforceScanTruncated: boolean;
  workOrderScanTruncated: boolean;
  partialFailures: string[];
  limits: Record<string, number>;
};

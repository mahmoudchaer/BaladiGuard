export type WorkforceAssigneeKind = 'worker' | 'team';

export type WorkforceWorker = {
  workerId: string;
  municipalityId: string;
  displayName: string;
  departmentIds: string[];
  teamIds: string[];
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type WorkforceTeam = {
  teamId: string;
  municipalityId: string;
  displayName: string;
  departmentIds: string[];
  workerIds: string[];
  leadWorkerId?: string | null;
  active: boolean;
  createdAt: string;
  updatedAt: string;
};

export type WorkloadCounts = {
  queued: number;
  assigned: number;
  inProgress: number;
  dueSoon: number;
  overdue: number;
  completed?: number;
  cancelled?: number;
};

export type WorkloadTicketRef = {
  ticketId: string;
  ticketNumber: string;
  status: string;
  departmentId?: string | null;
  slaState?: string | null;
};

export type WorkloadSubject = {
  id: string;
  kind: WorkforceAssigneeKind;
  displayName: string;
  departmentIds: string[];
  active: boolean;
  counts: WorkloadCounts;
  tickets: WorkloadTicketRef[];
};

export type WorkloadSnapshot = {
  municipalityId: string;
  unassigned: WorkloadCounts;
  unassignedTickets: WorkloadTicketRef[];
  workers: WorkloadSubject[];
  teams: WorkloadSubject[];
};

export type WorkOrderState = 'QUEUED' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export type WorkOrder = {
  workOrderId: string;
  ticketId: string;
  municipalityId: string;
  departmentId: string;
  state: WorkOrderState;
  summary: string;
  assignedWorkerId?: string | null;
  assignedTeamId?: string | null;
  createdAt: string;
  createdBy: string;
  updatedAt: string;
  updatedBy: string;
  startedAt?: string | null;
  startedBy?: string | null;
  completedAt?: string | null;
  completedBy?: string | null;
  cancelledAt?: string | null;
  cancelledBy?: string | null;
  cancelReasonCode?: string | null;
  completionNote?: string | null;
  cancelNote?: string | null;
  ticketStatus?: string | null;
  created?: boolean;
};

export type WorkOrderList = {
  items: WorkOrder[];
  activeWorkOrderId: string | null;
};

export type TicketOutcome = {
  resolutionReasonCode?: string | null;
  resolutionCitizenMessage?: string | null;
  resolutionNote?: string | null;
  resolvedAt?: string | null;
  resolvedBy?: string | null;
  closureReasonCode?: string | null;
  closureCitizenMessage?: string | null;
  closureNote?: string | null;
  closedAt?: string | null;
  closedBy?: string | null;
};

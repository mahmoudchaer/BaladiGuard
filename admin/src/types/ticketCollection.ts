/** Lightweight staff collection types aligned with backend staff_ticket_collection (#267). */

import type { ContentSafetyStatus, TicketPriority, TicketStatus } from '@/types/ticket';

export type TicketListItem = {
  ticketId: string;
  ticketNumber: string | null;
  status: TicketStatus;
  category: string;
  priority: TicketPriority | null;
  departmentId: string | null;
  department: {
    departmentId: string | null;
    name: string | null;
  } | null;
  summary: string;
  createdAt: string;
  updatedAt: string | null;
  municipalityId: string | null;
  assignmentState: 'assigned' | 'unassigned';
  assignedWorkerId?: string | null;
  assignedTeamId?: string | null;
  contentSafetyStatus?: ContentSafetyStatus;
  location: {
    latitude: number;
    longitude: number;
    addressText: string;
  };
};

export type TicketListPage = {
  items: TicketListItem[];
  nextCursor: string | null;
  previousCursor: string | null;
  limit: number;
  scannedCount: number | null;
  approximateTotal: number | null;
  freshnessHintSeconds: number;
};

export type TicketMapMarker = {
  ticketId: string;
  ticketNumber: string | null;
  status: TicketStatus;
  priority: TicketPriority | null;
  latitude: number;
  longitude: number;
  category: string;
};

export type TicketMapCluster = {
  id: string;
  latitude: number;
  longitude: number;
  count: number;
};

export type TicketMapViewport = {
  markers: TicketMapMarker[];
  clusters: TicketMapCluster[];
  limit: number;
  truncated: boolean;
  zoom: number;
};

export type TicketAggregates = {
  openCount: number;
  criticalCount: number;
  highCount: number;
  unassignedCount: number;
  overdueCount: number;
  queuedCount?: number;
  assignedCount?: number;
  inProgressCount?: number;
  dueSoonCount?: number;
  completedCount?: number;
  cancelledCount?: number;
  workforceUnassignedCount?: number;
  approximate: boolean;
};

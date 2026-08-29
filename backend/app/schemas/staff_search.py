"""Public, permission-scoped staff global search models (issue #42 / #260)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StaffSearchResultType = Literal["ticket", "worker", "team", "work_order"]


class StaffSearchTicketHit(BaseModel):
    result_type: Literal["ticket"] = Field(default="ticket", alias="resultType")
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str = Field(alias="ticketNumber")
    tracking_code: str | None = Field(default=None, alias="trackingCode")
    status: str
    category: str
    public_location_label: str | None = Field(default=None, alias="publicLocationLabel")

    model_config = {"populate_by_name": True}


class StaffSearchWorkerHit(BaseModel):
    result_type: Literal["worker"] = Field(default="worker", alias="resultType")
    worker_id: str = Field(alias="workerId")
    display_name: str = Field(alias="displayName")
    department_ids: list[str] = Field(alias="departmentIds")
    active: bool

    model_config = {"populate_by_name": True}


class StaffSearchTeamHit(BaseModel):
    result_type: Literal["team"] = Field(default="team", alias="resultType")
    team_id: str = Field(alias="teamId")
    display_name: str = Field(alias="displayName")
    department_ids: list[str] = Field(alias="departmentIds")
    active: bool

    model_config = {"populate_by_name": True}


class StaffSearchWorkOrderHit(BaseModel):
    result_type: Literal["work_order"] = Field(default="work_order", alias="resultType")
    work_order_id: str = Field(alias="workOrderId")
    ticket_id: str = Field(alias="ticketId")
    ticket_number: str | None = Field(default=None, alias="ticketNumber")
    state: str
    summary: str

    model_config = {"populate_by_name": True}


class StaffSearchResponse(BaseModel):
    as_of: str = Field(alias="asOf")
    query: str
    tickets: list[StaffSearchTicketHit] = Field(default_factory=list)
    workers: list[StaffSearchWorkerHit] = Field(default_factory=list)
    teams: list[StaffSearchTeamHit] = Field(default_factory=list)
    work_orders: list[StaffSearchWorkOrderHit] = Field(default_factory=list, alias="workOrders")
    tickets_truncated: bool = Field(default=False, alias="ticketsTruncated")
    workers_truncated: bool = Field(default=False, alias="workersTruncated")
    teams_truncated: bool = Field(default=False, alias="teamsTruncated")
    work_orders_truncated: bool = Field(default=False, alias="workOrdersTruncated")
    scan_truncated: bool = Field(default=False, alias="scanTruncated")
    workforce_scan_truncated: bool = Field(default=False, alias="workforceScanTruncated")
    work_order_scan_truncated: bool = Field(default=False, alias="workOrderScanTruncated")
    partial_failures: list[str] = Field(default_factory=list, alias="partialFailures")
    limits: dict[str, int] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

"""Persisted citizen contribution ledger and ranking projection (issue #323)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RewardCredit = Literal["pending", "confirmed"]
RewardActorType = Literal["system", "staff", "operator", "citizen"]


class StoredRewardEvent(BaseModel):
    """One immutable ledger row. Totals are derived; this row is never silently mutated."""

    event_id: str = Field(alias="eventId")
    event_key: str = Field(alias="eventKey")
    citizen_user_id: str = Field(alias="citizenUserId")
    ticket_id: str | None = Field(default=None, alias="ticketId")
    rule_version: str = Field(alias="ruleVersion")
    delta: int
    reason_code: str = Field(alias="reasonCode")
    credit: RewardCredit
    created_at: str = Field(alias="createdAt")
    reverses_event_id: str | None = Field(default=None, alias="reversesEventId")
    actor_type: RewardActorType = Field(default="system", alias="actorType")
    actor_id: str | None = Field(default=None, alias="actorId")
    note: str | None = None

    model_config = {"populate_by_name": True}


class StoredRewardProjection(BaseModel):
    """Rebuildable ranking snapshot derived from the ledger."""

    citizen_user_id: str = Field(alias="citizenUserId")
    confirmed_points_all_time: int = Field(default=0, alias="confirmedPointsAllTime")
    confirmed_points_monthly: int = Field(default=0, alias="confirmedPointsMonthly")
    monthly_period_key: str = Field(alias="monthlyPeriodKey")
    pending_points: int = Field(default=0, alias="pendingPoints")
    first_award_at: str | None = Field(default=None, alias="firstAwardAt")
    last_award_at: str | None = Field(default=None, alias="lastAwardAt")
    withdrawn: bool = False
    public_eligible: bool = Field(default=False, alias="publicEligible")
    public_display_name: str | None = Field(default=None, alias="publicDisplayName")
    leaderboard_opt_in: bool = Field(default=False, alias="leaderboardOptIn")
    public_name_visible: bool = Field(default=False, alias="publicNameVisible")
    public_board_key: str = Field(default="hidden", alias="publicBoardKey")
    monthly_board_key: str = Field(alias="monthlyBoardKey")
    all_time_sort_key: str = Field(alias="allTimeSortKey")
    monthly_sort_key: str = Field(alias="monthlySortKey")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

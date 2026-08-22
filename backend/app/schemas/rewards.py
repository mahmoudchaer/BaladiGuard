"""Citizen, public, and ops API schemas for verified contribution rewards (issue #323)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LeaderboardPeriod = Literal["all-time", "monthly"]
CitizenRewardReason = Literal[
    "accepted",
    "in_progress",
    "resolved",
    "supporting",
    "reviewing",
    "adjusted",
    "adjustment",
]


class RewardRuleItem(BaseModel):
    reason_code: str = Field(alias="reasonCode")
    points: int
    credit: Literal["pending", "confirmed"]
    summary: str

    model_config = {"populate_by_name": True}


class RewardLevelItem(BaseModel):
    id: str
    min_points: int = Field(alias="minPoints")
    title: str

    model_config = {"populate_by_name": True}


class RewardsRulesResponse(BaseModel):
    rule_version: str = Field(alias="ruleVersion")
    recognition_only: bool = Field(alias="recognitionOnly")
    rules: list[RewardRuleItem]
    levels: list[RewardLevelItem]
    notes: list[str]

    model_config = {"populate_by_name": True}


class RewardParticipation(BaseModel):
    opted_in: bool = Field(alias="optedIn")
    public_name_visible: bool = Field(alias="publicNameVisible")
    has_display_name: bool = Field(alias="hasDisplayName")
    eligible: bool
    missing: list[str]

    model_config = {"populate_by_name": True}


class CitizenRewardEvent(BaseModel):
    created_at: str = Field(alias="createdAt")
    delta: int
    reason: CitizenRewardReason
    credit: Literal["pending", "confirmed"]
    ticket_number: str | None = Field(default=None, alias="ticketNumber")

    model_config = {"populate_by_name": True}


class CitizenRewardsResponse(BaseModel):
    rule_version: str = Field(alias="ruleVersion")
    confirmed_points: int = Field(alias="confirmedPoints")
    pending_points: int = Field(alias="pendingPoints")
    monthly_points: int = Field(alias="monthlyPoints")
    monthly_period: str = Field(alias="monthlyPeriod")
    level_id: str = Field(alias="levelId")
    level_title: str = Field(alias="levelTitle")
    next_level_id: str | None = Field(default=None, alias="nextLevelId")
    next_level_title: str | None = Field(default=None, alias="nextLevelTitle")
    points_to_next_level: int | None = Field(default=None, alias="pointsToNextLevel")
    badges: list[str]
    private_rank_all_time: int | None = Field(default=None, alias="privateRankAllTime")
    private_rank_monthly: int | None = Field(default=None, alias="privateRankMonthly")
    public_rank_all_time: int | None = Field(default=None, alias="publicRankAllTime")
    public_rank_monthly: int | None = Field(default=None, alias="publicRankMonthly")
    participation: RewardParticipation
    recent_events: list[CitizenRewardEvent] = Field(alias="recentEvents")
    recognition_only: bool = Field(alias="recognitionOnly")

    model_config = {"populate_by_name": True}


class RewardsSettingsUpdateRequest(BaseModel):
    leaderboard_opt_in: bool = Field(alias="leaderboardOptIn")

    model_config = {"populate_by_name": True}


class PublicLeaderboardEntry(BaseModel):
    rank: int
    display_name: str = Field(alias="displayName")
    points: int
    level_title: str = Field(alias="levelTitle")

    model_config = {"populate_by_name": True}


class PublicLeaderboardResponse(BaseModel):
    period: LeaderboardPeriod
    period_key: str = Field(alias="periodKey")
    items: list[PublicLeaderboardEntry]
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    limit: int
    rule_version: str = Field(alias="ruleVersion")
    recognition_only: bool = Field(alias="recognitionOnly")

    model_config = {"populate_by_name": True}


class OpsRewardLedgerItem(BaseModel):
    event_id: str = Field(alias="eventId")
    event_key: str = Field(alias="eventKey")
    ticket_id: str | None = Field(default=None, alias="ticketId")
    rule_version: str = Field(alias="ruleVersion")
    delta: int
    reason_code: str = Field(alias="reasonCode")
    credit: Literal["pending", "confirmed"]
    created_at: str = Field(alias="createdAt")
    reverses_event_id: str | None = Field(default=None, alias="reversesEventId")
    actor_type: str = Field(alias="actorType")
    actor_id: str | None = Field(default=None, alias="actorId")
    note: str | None = None

    model_config = {"populate_by_name": True}


class OpsCitizenRewardsResponse(BaseModel):
    citizen_user_id: str = Field(alias="citizenUserId")
    withdrawn: bool
    confirmed_points: int = Field(alias="confirmedPoints")
    pending_points: int = Field(alias="pendingPoints")
    monthly_points: int = Field(alias="monthlyPoints")
    public_eligible: bool = Field(alias="publicEligible")
    events: list[OpsRewardLedgerItem]

    model_config = {"populate_by_name": True}


class OpsRewardAdjustmentRequest(BaseModel):
    citizen_user_id: str = Field(alias="citizenUserId", min_length=1, max_length=80)
    delta: int = Field(ge=-200, le=200)
    reason: str = Field(min_length=12, max_length=400)

    model_config = {"populate_by_name": True}

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 12:
            raise ValueError("reason must be at least 12 characters.")
        return trimmed

    @field_validator("delta")
    @classmethod
    def validate_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("delta must be a non-zero point correction.")
        return value


class CitizenRewardsExport(BaseModel):
    confirmed_points: int = Field(alias="confirmedPoints")
    pending_points: int = Field(alias="pendingPoints")
    monthly_points: int = Field(alias="monthlyPoints")
    events: list[CitizenRewardEvent]

    model_config = {"populate_by_name": True}

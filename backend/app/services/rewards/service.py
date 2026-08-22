"""Auditable citizen contribution ledger and ranking (issue #323)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.core.staff_auth import DEFAULT_SECRET_KEY
from app.database.store_factory import (
    get_citizen_store,
    get_duplicate_group_store,
    get_rewards_ledger_store,
    get_rewards_projection_store,
    get_ticket_store,
)
from app.schemas.citizen import StoredCitizenUser
from app.schemas.rewards import (
    CitizenRewardEvent,
    CitizenRewardsExport,
    CitizenRewardsResponse,
    OpsCitizenRewardsResponse,
    OpsRewardAdjustmentRequest,
    OpsRewardLedgerItem,
    PublicLeaderboardEntry,
    PublicLeaderboardResponse,
    RewardLevelItem,
    RewardParticipation,
    RewardRuleItem,
    RewardsRulesResponse,
)
from app.schemas.stored_rewards import StoredRewardEvent, StoredRewardProjection
from app.schemas.stored_ticket import StoredTicket
from app.services.citizens.service import is_anonymized_citizen, is_contribution_ready
from app.services.rewards.rules import (
    ABUSE_CONFIRMED_AWARD_LIMIT_24H,
    POINTS,
    REASON_IN_PROGRESS,
    REASON_MUNICIPALITY_ACCEPTED,
    REASON_OPS_CORRECTION,
    REASON_RESOLVED,
    REASON_REVERSAL_MERGED,
    REASON_REVERSAL_REJECTED,
    REASON_REVERSAL_REOPENED,
    REASON_REVERSAL_SAFETY,
    REASON_SAFETY_CLEARED,
    REASON_SUPPORTING_EVIDENCE,
    RULE_VERSION,
    award_event_key,
    citizen_reason,
    earned_badges,
    level_for_points,
    monthly_period_key,
    next_level,
    ops_event_key,
    ranking_sort_key,
    reversal_event_key,
    sanitize_public_display_name,
)

logger = logging.getLogger(__name__)

LEADERBOARD_DEFAULT_LIMIT = 20
LEADERBOARD_MAX_LIMIT = 50
RECENT_EVENT_LIMIT = 20

RULE_SUMMARIES = {
    REASON_MUNICIPALITY_ACCEPTED: "Municipality staff accepted the report into the work queue.",
    REASON_IN_PROGRESS: "Work started on a verified report.",
    REASON_RESOLVED: "A verified report was resolved.",
    REASON_SUPPORTING_EVIDENCE: "A related report was merged as supporting evidence.",
    REASON_SAFETY_CLEARED: "A report cleared automated review and is waiting for municipal work.",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cursor_secret() -> bytes:
    return (get_settings().secret_key or DEFAULT_SECRET_KEY).encode("utf-8")


def _opaque_rank_token(citizen_user_id: str) -> str:
    return hmac.new(
        _cursor_secret(),
        f"rewards-rank:{citizen_user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def _encode_cursor(*, points: int, first_award_at: str, citizen_user_id: str) -> str:
    inner = json.dumps(
        {
            "p": points,
            "t": first_award_at,
            "k": _opaque_rank_token(citizen_user_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(_cursor_secret(), inner, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(inner + b"." + signature).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode(cursor + padding)
    payload, separator, signature = raw.rpartition(b".")
    if not separator or len(signature) != hashlib.sha256().digest_size:
        raise ValueError("invalid cursor")
    expected = hmac.new(_cursor_secret(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid cursor")
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("invalid cursor")
    if any(key in parsed for key in ("u", "userId", "citizenUserId", "citizen_user_id")):
        raise ValueError("invalid cursor")
    return parsed


class RewardsServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class RewardsService:
    def _ledger(self):
        return get_rewards_ledger_store()

    def _projections(self):
        return get_rewards_projection_store()

    def _citizens(self):
        return get_citizen_store()

    def _tickets(self):
        return get_ticket_store()

    def _groups(self):
        return get_duplicate_group_store()

    def rules(self) -> RewardsRulesResponse:
        from app.services.rewards.rules import LEVELS

        return RewardsRulesResponse(
            ruleVersion=RULE_VERSION,
            recognitionOnly=True,
            rules=[
                RewardRuleItem(
                    reasonCode=reason,
                    points=POINTS[reason],
                    credit="pending" if reason == REASON_SAFETY_CLEARED else "confirmed",
                    summary=RULE_SUMMARIES[reason],
                )
                for reason in (
                    REASON_SAFETY_CLEARED,
                    REASON_MUNICIPALITY_ACCEPTED,
                    REASON_IN_PROGRESS,
                    REASON_RESOLVED,
                    REASON_SUPPORTING_EVIDENCE,
                )
            ],
            levels=[
                RewardLevelItem(id=level_id, minPoints=minimum, title=title)
                for level_id, minimum, title in LEVELS
            ],
            notes=[
                "Points reward verified civic value, not raw submission count.",
                "Submitting a report does not award confirmed points.",
                "Automated review can hold pending credit; it cannot take confirmed points.",
                "Recognition only — no money, wallets, or government benefits.",
                "The public board is opt-in and never shows phone, email, address, or tickets.",
            ],
        )

    def sync_ticket(self, ticket: StoredTicket, *, now: datetime | None = None) -> None:
        if not ticket.owner_user_id:
            return
        citizen = self._citizens().get(ticket.owner_user_id)
        if citizen is None or not citizen.active or is_anonymized_citizen(citizen):
            self.refresh_public_eligibility(ticket.owner_user_id, now=now)
            return
        if not is_contribution_ready(citizen):
            return

        moment = now or _utcnow()
        desired = self._desired_awards(ticket)
        existing = self._active_ticket_awards(ticket.ticket_id, citizen.user_id)
        existing_reasons = {event.reason_code for event in existing}

        for event in existing:
            if event.reason_code not in desired:
                self._reverse_event(
                    event,
                    reason_code=self._reversal_reason(ticket, event.reason_code),
                    now=moment,
                )

        for reason_code, credit in desired.items():
            if reason_code in existing_reasons:
                continue
            self._award(
                citizen_user_id=citizen.user_id,
                ticket_id=ticket.ticket_id,
                reason_code=reason_code,
                credit=credit,
                now=moment,
            )
        self.refresh_public_eligibility(citizen.user_id, now=moment)

    def withdraw_public(self, citizen_user_id: str, *, now: datetime | None = None) -> None:
        self.refresh_public_eligibility(citizen_user_id, now=now, force_withdrawn=True)

    def refresh_public_eligibility(
        self,
        citizen_user_id: str,
        *,
        now: datetime | None = None,
        force_withdrawn: bool | None = None,
    ) -> StoredRewardProjection:
        citizen = self._citizens().get(citizen_user_id)
        withdrawn = bool(force_withdrawn)
        if citizen is None or not citizen.active or (citizen and is_anonymized_citizen(citizen)):
            withdrawn = True
        return self._rebuild_projection(
            citizen_user_id, citizen=citizen, withdrawn=withdrawn, now=now
        )

    def get_citizen_rewards(self, citizen_user_id: str) -> CitizenRewardsResponse:
        citizen = self._require_active_citizen(citizen_user_id)
        projection = self.refresh_public_eligibility(citizen_user_id)
        events = self._ledger().list_by_citizen(citizen_user_id)
        ticket_numbers = self._ticket_numbers(
            [event.ticket_id for event in events if event.ticket_id]
        )
        recent = [
            self._to_citizen_event(event, ticket_numbers)
            for event in reversed(events[-RECENT_EVENT_LIMIT:])
            if citizen_reason(event.reason_code)
        ]
        level_id, level_title = level_for_points(projection.confirmed_points_all_time)
        upcoming = next_level(projection.confirmed_points_all_time)
        period_key = monthly_period_key(_iso(_utcnow()))
        private_all = self._rank_among(
            citizen_user_id, public_only=False, period="all-time", period_key=period_key
        )
        private_month = self._rank_among(
            citizen_user_id, public_only=False, period="monthly", period_key=period_key
        )
        public_all = (
            self._rank_among(
                citizen_user_id, public_only=True, period="all-time", period_key=period_key
            )
            if projection.public_eligible
            else None
        )
        public_month = (
            self._rank_among(
                citizen_user_id, public_only=True, period="monthly", period_key=period_key
            )
            if projection.public_eligible
            else None
        )
        return CitizenRewardsResponse(
            ruleVersion=RULE_VERSION,
            confirmedPoints=projection.confirmed_points_all_time,
            pendingPoints=projection.pending_points,
            monthlyPoints=projection.confirmed_points_monthly,
            monthlyPeriod=projection.monthly_period_key,
            levelId=level_id,
            levelTitle=level_title,
            nextLevelId=upcoming[0] if upcoming else None,
            nextLevelTitle=upcoming[1] if upcoming else None,
            pointsToNextLevel=upcoming[2] if upcoming else None,
            badges=earned_badges(projection.confirmed_points_all_time),
            privateRankAllTime=private_all,
            privateRankMonthly=private_month,
            publicRankAllTime=public_all,
            publicRankMonthly=public_month,
            participation=self._participation(citizen),
            recentEvents=recent,
            recognitionOnly=True,
        )

    def export_rewards(self, citizen_user_id: str) -> CitizenRewardsExport:
        projection = self.refresh_public_eligibility(citizen_user_id)
        events = self._ledger().list_by_citizen(citizen_user_id)
        ticket_numbers = self._ticket_numbers(
            [event.ticket_id for event in events if event.ticket_id]
        )
        return CitizenRewardsExport(
            confirmedPoints=projection.confirmed_points_all_time,
            pendingPoints=projection.pending_points,
            monthlyPoints=projection.confirmed_points_monthly,
            events=[self._to_citizen_event(event, ticket_numbers) for event in events],
        )

    def public_leaderboard(
        self,
        *,
        period: str,
        cursor: str | None,
        limit: int,
    ) -> PublicLeaderboardResponse:
        if period not in {"all-time", "monthly"}:
            raise RewardsServiceError("VALIDATION_ERROR", "period must be all-time or monthly.")
        page_size = max(1, min(limit, LEADERBOARD_MAX_LIMIT))
        period_key = monthly_period_key(_iso(_utcnow()))
        ranked = self._projections().list_ranked(
            public_only=True, period=period, period_key=period_key
        )
        start = 0
        if cursor:
            try:
                payload = _decode_cursor(cursor)
                start = self._cursor_index(ranked, payload, period=period)
            except Exception as exc:
                raise RewardsServiceError("VALIDATION_ERROR", "cursor is invalid.") from exc
        page = ranked[start : start + page_size]
        items: list[PublicLeaderboardEntry] = []
        for offset, projection in enumerate(page):
            points = (
                projection.confirmed_points_monthly
                if period == "monthly"
                else projection.confirmed_points_all_time
            )
            _level_id, level_title = level_for_points(points)
            items.append(
                PublicLeaderboardEntry(
                    rank=start + offset + 1,
                    displayName=projection.public_display_name or "Community member",
                    points=points,
                    levelTitle=level_title,
                )
            )
        next_cursor = None
        if start + page_size < len(ranked):
            nxt = ranked[start + page_size]
            next_cursor = _encode_cursor(
                points=(
                    nxt.confirmed_points_monthly
                    if period == "monthly"
                    else nxt.confirmed_points_all_time
                ),
                first_award_at=nxt.first_award_at or "",
                citizen_user_id=nxt.citizen_user_id,
            )
        return PublicLeaderboardResponse(
            period=period,  # type: ignore[arg-type]
            periodKey="all-time" if period == "all-time" else period_key,
            items=items,
            nextCursor=next_cursor,
            limit=page_size,
            ruleVersion=RULE_VERSION,
            recognitionOnly=True,
        )

    def ops_citizen_ledger(self, citizen_user_id: str) -> OpsCitizenRewardsResponse:
        projection = self.refresh_public_eligibility(citizen_user_id)
        events = self._ledger().list_by_citizen(citizen_user_id)
        return OpsCitizenRewardsResponse(
            citizenUserId=citizen_user_id,
            withdrawn=projection.withdrawn,
            confirmedPoints=projection.confirmed_points_all_time,
            pendingPoints=projection.pending_points,
            monthlyPoints=projection.confirmed_points_monthly,
            publicEligible=projection.public_eligible,
            events=[
                OpsRewardLedgerItem(
                    eventId=event.event_id,
                    eventKey=event.event_key,
                    ticketId=event.ticket_id,
                    ruleVersion=event.rule_version,
                    delta=event.delta,
                    reasonCode=event.reason_code,
                    credit=event.credit,
                    createdAt=event.created_at,
                    reversesEventId=event.reverses_event_id,
                    actorType=event.actor_type,
                    actorId=event.actor_id,
                    note=event.note,
                )
                for event in events
            ],
        )

    def apply_ops_adjustment(
        self,
        payload: OpsRewardAdjustmentRequest,
        *,
        actor_id: str,
        now: datetime | None = None,
    ) -> OpsCitizenRewardsResponse:
        citizen = self._citizens().get(payload.citizen_user_id)
        if citizen is None:
            raise RewardsServiceError("NOT_FOUND", "Citizen was not found.", 404)
        moment = now or _utcnow()
        adjustment_id = f"adj_{secrets.token_hex(8)}"
        event = StoredRewardEvent(
            eventId=f"rew_{secrets.token_hex(12)}",
            eventKey=ops_event_key(
                citizen_user_id=payload.citizen_user_id, adjustment_id=adjustment_id
            ),
            citizenUserId=payload.citizen_user_id,
            ticketId=None,
            ruleVersion=RULE_VERSION,
            delta=payload.delta,
            reasonCode=REASON_OPS_CORRECTION,
            credit="confirmed",
            createdAt=_iso(moment),
            actorType="operator",
            actorId=actor_id,
            note=payload.reason,
        )
        self._ledger().put_if_absent(event)
        self.refresh_public_eligibility(payload.citizen_user_id, now=moment)
        return self.ops_citizen_ledger(payload.citizen_user_id)

    def _require_active_citizen(self, citizen_user_id: str) -> StoredCitizenUser:
        citizen = self._citizens().get(citizen_user_id)
        if citizen is None or not citizen.active or is_anonymized_citizen(citizen):
            raise RewardsServiceError("UNAUTHORIZED", "Citizen authentication required.", 401)
        return citizen

    def _desired_awards(self, ticket: StoredTicket) -> dict[str, str]:
        if self._is_merged_duplicate(ticket):
            return {REASON_SUPPORTING_EVIDENCE: "confirmed"}
        if self._is_cancelled(ticket):
            return {}
        desired: dict[str, str] = {}
        if ticket.content_safety_enrolled and ticket.content_safety_status == "passed":
            desired[REASON_SAFETY_CLEARED] = "pending"
        if self._staff_accepted(ticket):
            desired[REASON_MUNICIPALITY_ACCEPTED] = "confirmed"
        if self._work_started(ticket):
            desired[REASON_IN_PROGRESS] = "confirmed"
        if self._is_resolved(ticket):
            desired[REASON_RESOLVED] = "confirmed"
        return desired

    def _is_merged_duplicate(self, ticket: StoredTicket) -> bool:
        if not ticket.duplicate_group_id:
            return False
        group = self._groups().get(ticket.duplicate_group_id)
        if group is None:
            return False
        return group.canonical_ticket_id != ticket.ticket_id

    @staticmethod
    def _is_cancelled(ticket: StoredTicket) -> bool:
        return ticket.status == "CLOSED" and not ticket.resolved_at

    @staticmethod
    def _is_resolved(ticket: StoredTicket) -> bool:
        return ticket.status == "RESOLVED" or (
            ticket.status == "CLOSED" and bool(ticket.resolved_at)
        )

    @staticmethod
    def _staff_accepted(ticket: StoredTicket) -> bool:
        return ticket.status in {"ASSIGNED", "IN_PROGRESS", "RESOLVED"} or (
            ticket.status == "CLOSED" and bool(ticket.resolved_at)
        )

    @staticmethod
    def _work_started(ticket: StoredTicket) -> bool:
        return ticket.status in {"IN_PROGRESS", "RESOLVED"} or (
            ticket.status == "CLOSED" and bool(ticket.resolved_at)
        )

    def _reversal_reason(self, ticket: StoredTicket, award_reason: str) -> str:
        if self._is_merged_duplicate(ticket):
            return REASON_REVERSAL_MERGED
        if self._is_cancelled(ticket):
            return REASON_REVERSAL_REJECTED
        if award_reason == REASON_RESOLVED and not self._is_resolved(ticket):
            return REASON_REVERSAL_REOPENED
        if ticket.content_safety_enrolled and ticket.content_safety_status in {
            "rejected",
            "failed",
        }:
            return REASON_REVERSAL_SAFETY
        return REASON_REVERSAL_REJECTED

    def _active_ticket_awards(
        self, ticket_id: str, citizen_user_id: str
    ) -> list[StoredRewardEvent]:
        events = [
            event
            for event in self._ledger().list_by_ticket(ticket_id)
            if event.citizen_user_id == citizen_user_id
        ]
        reversed_ids = {event.reverses_event_id for event in events if event.reverses_event_id}
        return [
            event
            for event in events
            if event.delta > 0
            and event.event_id not in reversed_ids
            and not event.reverses_event_id
        ]

    def _award(
        self,
        *,
        citizen_user_id: str,
        ticket_id: str,
        reason_code: str,
        credit: str,
        now: datetime,
    ) -> StoredRewardEvent | None:
        if credit == "confirmed" and self._abuse_throttled(citizen_user_id, now):
            logger.info(
                "Skipping confirmed reward due to abuse throttle citizen=%s ticket=%s reason=%s",
                citizen_user_id,
                ticket_id,
                reason_code,
            )
            return None
        event = StoredRewardEvent(
            eventId=f"rew_{secrets.token_hex(12)}",
            eventKey=award_event_key(
                citizen_user_id=citizen_user_id,
                ticket_id=ticket_id,
                reason_code=reason_code,
            ),
            citizenUserId=citizen_user_id,
            ticketId=ticket_id,
            ruleVersion=RULE_VERSION,
            delta=POINTS[reason_code],
            reasonCode=reason_code,
            credit=credit,  # type: ignore[arg-type]
            createdAt=_iso(now),
            actorType="system",
        )
        stored = self._ledger().put_if_absent(event)
        self._rebuild_projection(citizen_user_id, now=now)
        return stored

    def _reverse_event(
        self,
        event: StoredRewardEvent,
        *,
        reason_code: str,
        now: datetime,
    ) -> None:
        reversal = StoredRewardEvent(
            eventId=f"rew_{secrets.token_hex(12)}",
            eventKey=reversal_event_key(
                citizen_user_id=event.citizen_user_id,
                ticket_id=event.ticket_id,
                reason_code=reason_code,
                original_event_id=event.event_id,
            ),
            citizenUserId=event.citizen_user_id,
            ticketId=event.ticket_id,
            ruleVersion=RULE_VERSION,
            delta=-event.delta,
            reasonCode=reason_code,
            credit=event.credit,
            createdAt=_iso(now),
            reversesEventId=event.event_id,
            actorType="system",
        )
        self._ledger().put_if_absent(reversal)
        self._rebuild_projection(event.citizen_user_id, now=now)

    def _abuse_throttled(self, citizen_user_id: str, now: datetime) -> bool:
        cutoff = now - timedelta(hours=24)
        events = self._ledger().list_by_citizen(citizen_user_id)
        recent = 0
        for event in events:
            if event.credit != "confirmed" or event.delta <= 0 or event.reverses_event_id:
                continue
            if event.reason_code == REASON_OPS_CORRECTION:
                continue
            try:
                created = _parse_iso(event.created_at)
            except ValueError:
                continue
            if created >= cutoff:
                recent += 1
        return recent >= ABUSE_CONFIRMED_AWARD_LIMIT_24H

    def _rebuild_projection(
        self,
        citizen_user_id: str,
        *,
        citizen: StoredCitizenUser | None = None,
        withdrawn: bool = False,
        now: datetime | None = None,
    ) -> StoredRewardProjection:
        moment = now or _utcnow()
        stamped = _iso(moment)
        period_key = monthly_period_key(stamped)
        events = self._ledger().list_by_citizen(citizen_user_id)
        confirmed = 0
        pending = 0
        monthly = 0
        first_award_at: str | None = None
        last_award_at: str | None = None
        reversed_ids = {event.reverses_event_id for event in events if event.reverses_event_id}
        for event in events:
            if event.credit == "confirmed":
                confirmed += event.delta
                if monthly_period_key(event.created_at) == period_key:
                    monthly += event.delta
            else:
                pending += event.delta
            if (
                event.credit == "confirmed"
                and event.delta > 0
                and event.event_id not in reversed_ids
                and not event.reverses_event_id
            ):
                if first_award_at is None or event.created_at < first_award_at:
                    first_award_at = event.created_at
                if last_award_at is None or event.created_at > last_award_at:
                    last_award_at = event.created_at
        if confirmed <= 0:
            first_award_at = None
            last_award_at = None
            monthly = min(monthly, 0) if monthly < 0 else 0
        user = citizen if citizen is not None else self._citizens().get(citizen_user_id)
        participation = self._participation(user) if user and not withdrawn else None
        display_name = (
            sanitize_public_display_name(user.full_name)
            if user and participation and participation.eligible
            else None
        )
        public_eligible = bool(
            participation and participation.eligible and not withdrawn and confirmed > 0
        )
        sort_at = first_award_at or "9999-12-31T00:00:00Z"
        projection = StoredRewardProjection(
            citizenUserId=citizen_user_id,
            confirmedPointsAllTime=confirmed,
            confirmedPointsMonthly=max(monthly, 0) if confirmed > 0 else 0,
            monthlyPeriodKey=period_key,
            pendingPoints=max(pending, 0),
            firstAwardAt=first_award_at,
            lastAwardAt=last_award_at,
            withdrawn=withdrawn,
            publicEligible=public_eligible,
            publicDisplayName=display_name,
            leaderboardOptIn=bool(user.leaderboard_opt_in) if user else False,
            publicNameVisible=bool(user.public_name_visible) if user else False,
            publicBoardKey="public" if public_eligible else "hidden",
            monthlyBoardKey=f"{'public' if public_eligible else 'hidden'}#{period_key}",
            allTimeSortKey=ranking_sort_key(
                points=confirmed if public_eligible else 0,
                first_award_at=sort_at,
                citizen_user_id=citizen_user_id,
            ),
            monthlySortKey=ranking_sort_key(
                points=max(monthly, 0) if public_eligible else 0,
                first_award_at=sort_at,
                citizen_user_id=citizen_user_id,
            ),
            updatedAt=stamped,
        )
        self._projections().save(projection)
        return projection

    def _participation(self, citizen: StoredCitizenUser | None) -> RewardParticipation:
        if citizen is None or not citizen.active or is_anonymized_citizen(citizen):
            return RewardParticipation(
                optedIn=False,
                publicNameVisible=False,
                hasDisplayName=False,
                eligible=False,
                missing=["account"],
            )
        display_name = sanitize_public_display_name(citizen.full_name)
        missing: list[str] = []
        if not citizen.leaderboard_opt_in:
            missing.append("leaderboardOptIn")
        if not citizen.public_name_visible:
            missing.append("publicNameVisible")
        if not display_name:
            missing.append("displayName")
        return RewardParticipation(
            optedIn=citizen.leaderboard_opt_in,
            publicNameVisible=citizen.public_name_visible,
            hasDisplayName=bool(display_name),
            eligible=not missing,
            missing=missing,
        )

    def _ticket_numbers(self, ticket_ids: list[str]) -> dict[str, str]:
        numbers: dict[str, str] = {}
        store = self._tickets()
        for ticket_id in dict.fromkeys(ticket_ids):
            ticket = store.get(ticket_id)
            if ticket is not None:
                numbers[ticket_id] = ticket.ticket_number
        return numbers

    def _to_citizen_event(
        self, event: StoredRewardEvent, ticket_numbers: dict[str, str]
    ) -> CitizenRewardEvent:
        return CitizenRewardEvent(
            createdAt=event.created_at,
            delta=event.delta,
            reason=citizen_reason(event.reason_code),
            credit=event.credit,
            ticketNumber=ticket_numbers.get(event.ticket_id) if event.ticket_id else None,
        )

    def _rank_among(
        self,
        citizen_user_id: str,
        *,
        public_only: bool,
        period: str,
        period_key: str,
    ) -> int | None:
        ranked = self._projections().list_ranked(
            public_only=public_only, period=period, period_key=period_key
        )
        for index, item in enumerate(ranked, start=1):
            if item.citizen_user_id == citizen_user_id:
                return index
        return None

    def _cursor_index(
        self,
        ranked: list[StoredRewardProjection],
        payload: dict[str, Any],
        *,
        period: str,
    ) -> int:
        token = str(payload.get("k") or "")
        if len(token) != 16:
            raise ValueError("invalid cursor")
        for index, item in enumerate(ranked):
            expected = _opaque_rank_token(item.citizen_user_id)
            if hmac.compare_digest(expected, token):
                return index
        points = int(payload.get("p") or 0)
        first_at = str(payload.get("t") or "")
        for index, item in enumerate(ranked):
            item_points = (
                item.confirmed_points_monthly
                if period == "monthly"
                else item.confirmed_points_all_time
            )
            item_token = _opaque_rank_token(item.citizen_user_id)
            if (-item_points, item.first_award_at or "9999", item_token) >= (
                -points,
                first_at or "9999",
                token,
            ):
                return index
        return len(ranked)


rewards_service = RewardsService()

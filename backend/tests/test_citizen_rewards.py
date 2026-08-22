"""Verified citizen rewards and public leaderboard (issue #323)."""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.database.memory_duplicate_group import duplicate_group_store
from app.schemas.citizen import CitizenProfileUpdateRequest
from app.schemas.stored_duplicate_group import StoredDuplicateGroup
from app.schemas.stored_ticket import StoredTicket
from app.schemas.ticket import ReportContact, ReportLocation
from app.services.citizens.service import citizen_service
from app.services.rewards.rules import (
    POINTS,
    REASON_IN_PROGRESS,
    REASON_MUNICIPALITY_ACCEPTED,
    REASON_RESOLVED,
    REASON_SUPPORTING_EVIDENCE,
    RULE_VERSION,
)
from app.services.rewards.service import rewards_service
from tests.conftest import contribution_ready_auth_headers, ensure_contribution_ready_citizen
from tests.test_read_tickets import create_ticket


def _ticket(
    *,
    owner_id: str,
    ticket_id: str,
    status: str = "SUBMITTED",
    resolved_at: str | None = None,
    safety_status: str = "pending",
    enrolled: bool = True,
    duplicate_group_id: str | None = None,
    created_at: str | None = None,
) -> StoredTicket:
    stamped = created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ticket = StoredTicket(
        ticketId=ticket_id,
        ticketNumber=f"BG-{ticket_id[-6:]}",
        trackingCode=ticket_id[-6:].upper(),
        description="Pothole near the school entrance blocking traffic.",
        contact=ReportContact(name="Citizen", phone="+96170123456"),
        location=ReportLocation(
            latitude=33.89,
            longitude=35.5,
            addressText="Beirut",
            source="MANUAL",
        ),
        imageObjectKey="reports/mock/x.jpg",
        ownerUserId=owner_id,
        status=status,
        createdAt=stamped,
        updatedAt=stamped,
        resolvedAt=resolved_at,
        duplicateGroupId=duplicate_group_id,
        contentSafetyStatus=safety_status,
    )
    ticket.content_safety_enrolled = enrolled
    ticket_store.save(ticket)
    return ticket


def _opt_in(user_id: str, name: str = "Ada Citizen") -> None:
    citizen_service.update_profile(
        user_id,
        CitizenProfileUpdateRequest.model_validate(
            {
                "fullName": name,
                "publicNameVisible": True,
                "leaderboardOptIn": True,
            }
        ),
    )


def test_submit_does_not_award_confirmed_or_pending_points(anonymous_client: TestClient) -> None:
    headers = contribution_ready_auth_headers(phone="+96170111001")
    created = create_ticket(anonymous_client)
    rewards = anonymous_client.get("/v1/citizen/me/rewards", headers=headers)
    # create_ticket uses the default contribution-ready citizen, not +96170111001
    owner, token = ensure_contribution_ready_citizen()
    body = anonymous_client.get(
        "/v1/citizen/me/rewards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert body.status_code == 200, body.text
    payload = body.json()
    assert payload["confirmedPoints"] == 0
    assert payload["pendingPoints"] == 0
    assert created["status"] == "SUBMITTED"
    del rewards


def test_scoring_pending_then_confirmed_path_and_idempotent_retry() -> None:
    user, _token = ensure_contribution_ready_citizen(phone="+96170111002", full_name="Maya")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_reward_path")
    rewards_service.sync_ticket(ticket)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 0

    ticket = ticket.model_copy(update={"content_safety_status": "passed"})
    ticket.content_safety_enrolled = True
    ticket_store.save(ticket)
    rewards_service.sync_ticket(ticket)
    pending = rewards_service.get_citizen_rewards(user.user_id)
    assert pending.pending_points == POINTS["SAFETY_CLEARED"]
    assert pending.confirmed_points == 0

    ticket = ticket.model_copy(update={"status": "ASSIGNED"})
    ticket.content_safety_enrolled = True
    ticket_store.save(ticket)
    rewards_service.sync_ticket(ticket)
    rewards_service.sync_ticket(ticket)
    assigned = rewards_service.get_citizen_rewards(user.user_id)
    assert assigned.confirmed_points == POINTS[REASON_MUNICIPALITY_ACCEPTED]
    assert assigned.pending_points == POINTS["SAFETY_CLEARED"]

    ticket = ticket.model_copy(update={"status": "IN_PROGRESS"})
    ticket.content_safety_enrolled = True
    ticket_store.save(ticket)
    rewards_service.sync_ticket(ticket)
    ticket = ticket.model_copy(
        update={
            "status": "RESOLVED",
            "resolved_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    )
    ticket.content_safety_enrolled = True
    ticket_store.save(ticket)
    rewards_service.sync_ticket(ticket)
    resolved = rewards_service.get_citizen_rewards(user.user_id)
    assert resolved.confirmed_points == (
        POINTS[REASON_MUNICIPALITY_ACCEPTED] + POINTS[REASON_IN_PROGRESS] + POINTS[REASON_RESOLVED]
    )
    keys = [event.event_key for event in rewards_service._ledger().list_by_citizen(user.user_id)]
    assert len(keys) == len(set(keys))


def test_unowned_and_unready_tickets_are_ineligible() -> None:
    user, _token = ensure_contribution_ready_citizen(phone="+96170111003")
    orphan = _ticket(owner_id=None, ticket_id="tkt_reward_orphan")  # type: ignore[arg-type]
    orphan = orphan.model_copy(update={"owner_user_id": None, "status": "RESOLVED"})
    rewards_service.sync_ticket(orphan)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 0


def test_rejection_and_reopen_reverse_points() -> None:
    user, _token = ensure_contribution_ready_citizen(phone="+96170111004")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_reward_reverse", status="ASSIGNED")
    rewards_service.sync_ticket(ticket)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 10

    cancelled = ticket.model_copy(update={"status": "CLOSED", "resolved_at": None})
    ticket_store.save(cancelled)
    rewards_service.sync_ticket(cancelled)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 0

    ticket = _ticket(
        owner_id=user.user_id,
        ticket_id="tkt_reward_reopen",
        status="RESOLVED",
        resolved_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    rewards_service.sync_ticket(ticket)
    before = rewards_service.get_citizen_rewards(user.user_id).confirmed_points
    reopened = ticket.model_copy(update={"status": "IN_PROGRESS", "resolved_at": None})
    ticket_store.save(reopened)
    rewards_service.sync_ticket(reopened)
    after = rewards_service.get_citizen_rewards(user.user_id).confirmed_points
    assert before - after == POINTS[REASON_RESOLVED]


def test_merge_converts_duplicate_to_supporting_credit() -> None:
    user, _token = ensure_contribution_ready_citizen(phone="+96170111005")
    other, _other_token = ensure_contribution_ready_citizen(phone="+96170111006", full_name="Other")
    canonical = _ticket(owner_id=user.user_id, ticket_id="tkt_reward_can", status="ASSIGNED")
    duplicate = _ticket(owner_id=other.user_id, ticket_id="tkt_reward_dup", status="ASSIGNED")
    rewards_service.sync_ticket(canonical)
    rewards_service.sync_ticket(duplicate)
    assert rewards_service.get_citizen_rewards(other.user_id).confirmed_points == 10

    group = StoredDuplicateGroup(
        duplicateGroupId="dgrp_reward",
        canonicalTicketId=canonical.ticket_id,
        ticketIds=[canonical.ticket_id, duplicate.ticket_id],
        createdAt=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        createdBy="staff",
    )
    duplicate_group_store.save(group)
    merged = duplicate.model_copy(update={"duplicate_group_id": group.duplicate_group_id})
    ticket_store.save(merged)
    rewards_service.sync_ticket(merged)
    rewards_service.sync_ticket(canonical)
    assert (
        rewards_service.get_citizen_rewards(other.user_id).confirmed_points
        == POINTS[REASON_SUPPORTING_EVIDENCE]
    )
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 10


def test_automated_safety_reject_does_not_strip_staff_confirmed_points() -> None:
    user, _token = ensure_contribution_ready_citizen(phone="+96170111007")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_reward_safe", status="ASSIGNED")
    rewards_service.sync_ticket(ticket)
    rejected = ticket.model_copy(update={"content_safety_status": "rejected"})
    rejected.content_safety_enrolled = True
    ticket_store.save(rejected)
    rewards_service.sync_ticket(rejected)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 10


def test_public_leaderboard_is_opt_in_and_hides_identifiers(
    anonymous_client: TestClient,
) -> None:
    first, _ = ensure_contribution_ready_citizen(phone="+96170111008", full_name="Same Name")
    second, _ = ensure_contribution_ready_citizen(phone="+96170111009", full_name="Same Name")
    _ticket(owner_id=first.user_id, ticket_id="tkt_lb_1", status="ASSIGNED")
    _ticket(owner_id=second.user_id, ticket_id="tkt_lb_2", status="IN_PROGRESS")
    rewards_service.sync_ticket(ticket_store.get("tkt_lb_1"))
    rewards_service.sync_ticket(ticket_store.get("tkt_lb_2"))

    hidden = anonymous_client.get("/v1/rewards/leaderboard")
    assert hidden.status_code == 200
    assert hidden.json()["items"] == []

    _opt_in(first.user_id, "Same Name")
    _opt_in(second.user_id, "Same Name")
    public = anonymous_client.get("/v1/rewards/leaderboard?period=all-time&limit=20")
    assert public.status_code == 200
    body = public.json()
    assert body["recognitionOnly"] is True
    names = [item["displayName"] for item in body["items"]]
    assert names.count("Same Name") == 2
    serialized = str(body)
    assert first.user_id not in serialized
    assert second.user_id not in serialized
    assert "+961" not in serialized
    assert "email" not in serialized
    assert "ticketId" not in serialized
    assert body["items"][0]["points"] >= body["items"][1]["points"]


def test_leaderboard_pagination_and_ties(anonymous_client: TestClient) -> None:
    earlier = datetime.now(UTC) - timedelta(hours=2)
    later = datetime.now(UTC) - timedelta(hours=1)
    first, _ = ensure_contribution_ready_citizen(phone="+96170111010", full_name="Early Bird")
    second, _ = ensure_contribution_ready_citizen(phone="+96170111011", full_name="Late Bird")
    _opt_in(first.user_id, "Early Bird")
    _opt_in(second.user_id, "Late Bird")
    t1 = _ticket(
        owner_id=first.user_id,
        ticket_id="tkt_tie_1",
        status="ASSIGNED",
        created_at=earlier.isoformat().replace("+00:00", "Z"),
    )
    t2 = _ticket(
        owner_id=second.user_id,
        ticket_id="tkt_tie_2",
        status="ASSIGNED",
        created_at=later.isoformat().replace("+00:00", "Z"),
    )
    rewards_service.sync_ticket(t1, now=earlier)
    rewards_service.sync_ticket(t2, now=later)
    page = anonymous_client.get("/v1/rewards/leaderboard?limit=1")
    assert page.status_code == 200
    body = page.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["displayName"] == "Early Bird"
    assert body["nextCursor"]
    page2 = anonymous_client.get(f"/v1/rewards/leaderboard?limit=1&cursor={body['nextCursor']}")
    assert page2.status_code == 200
    assert page2.json()["items"][0]["displayName"] == "Late Bird"


def test_opt_out_and_deletion_remove_public_attribution(
    anonymous_client: TestClient,
) -> None:
    user, token = ensure_contribution_ready_citizen(
        phone="+96170111012", full_name="Private Person"
    )
    _opt_in(user.user_id, "Private Person")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_priv_1", status="ASSIGNED")
    rewards_service.sync_ticket(ticket)
    assert anonymous_client.get("/v1/rewards/leaderboard").json()["items"]

    citizen_service.update_profile(
        user.user_id,
        CitizenProfileUpdateRequest.model_validate({"leaderboardOptIn": False}),
    )
    assert anonymous_client.get("/v1/rewards/leaderboard").json()["items"] == []
    private = anonymous_client.get(
        "/v1/citizen/me/rewards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert private.status_code == 200
    assert private.json()["confirmedPoints"] == 10
    assert private.json()["participation"]["optedIn"] is False

    _opt_in(user.user_id, "Private Person")
    deleted = anonymous_client.post(
        "/v1/citizen/me/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert deleted.status_code == 200
    assert anonymous_client.get("/v1/rewards/leaderboard").json()["items"] == []


def test_abuse_throttle_skips_extra_confirmed_awards() -> None:
    user, _ = ensure_contribution_ready_citizen(phone="+96170111013")
    now = datetime.now(UTC)
    for index in range(8):
        ticket = _ticket(
            owner_id=user.user_id,
            ticket_id=f"tkt_abuse_{index}",
            status="ASSIGNED",
        )
        rewards_service.sync_ticket(ticket, now=now)
    extra = _ticket(owner_id=user.user_id, ticket_id="tkt_abuse_extra", status="ASSIGNED")
    rewards_service.sync_ticket(extra, now=now)
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 80


def test_ops_correction_is_audited_and_staff_cannot_use_it(
    anonymous_client: TestClient,
    operator_auth_headers: dict[str, str],
    staff_auth_headers: dict[str, str],
) -> None:
    user, _ = ensure_contribution_ready_citizen(phone="+96170111014")
    forbidden = anonymous_client.post(
        "/v1/ops/rewards/adjustments",
        headers=staff_auth_headers,
        json={
            "citizenUserId": user.user_id,
            "delta": 20,
            "reason": "Municipality bonus for a favorite resident.",
        },
    )
    assert forbidden.status_code in {401, 403}

    created = anonymous_client.post(
        "/v1/ops/rewards/adjustments",
        headers=operator_auth_headers,
        json={
            "citizenUserId": user.user_id,
            "delta": 15,
            "reason": "Appealed rejected report restored after review.",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["confirmedPoints"] == 15
    assert body["events"][0]["reasonCode"] == "OPS_CORRECTION"
    assert body["events"][0]["note"]
    ledger = anonymous_client.get(
        f"/v1/ops/rewards/citizens/{user.user_id}",
        headers=operator_auth_headers,
    )
    assert ledger.status_code == 200
    assert ledger.json()["events"][0]["actorType"] == "operator"


def test_rewards_authorization_and_profile_prompt(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/v1/citizen/me/rewards").status_code == 401
    user, token = ensure_contribution_ready_citizen(phone="+96170111015", full_name=None)
    headers = {"Authorization": f"Bearer {token}"}
    body = anonymous_client.get("/v1/citizen/me/rewards", headers=headers).json()
    assert "displayName" in body["participation"]["missing"]
    assert "leaderboardOptIn" in body["participation"]["missing"]
    assert body["participation"]["eligible"] is False
    patched = anonymous_client.patch(
        "/v1/citizen/me/rewards-settings",
        headers=headers,
        json={"leaderboardOptIn": True},
    )
    assert patched.status_code == 200
    assert patched.json()["leaderboardOptIn"] is True
    rules = anonymous_client.get("/v1/rewards/rules")
    assert rules.status_code == 200
    assert rules.json()["ruleVersion"] == RULE_VERSION
    assert rules.json()["recognitionOnly"] is True


def test_export_includes_private_rewards_without_abuse_internals(
    anonymous_client: TestClient,
) -> None:
    user, token = ensure_contribution_ready_citizen(phone="+96170111016", full_name="Export User")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_export_1", status="ASSIGNED")
    rewards_service.sync_ticket(ticket)
    exported = anonymous_client.get(
        "/v1/citizen/me/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert exported.status_code == 200
    body = exported.json()
    assert body["rewards"]["confirmedPoints"] == 10
    assert body["rewards"]["events"][0]["reason"] == "accepted"
    assert "ABUSE" not in str(body)
    assert "REVERSAL_ABUSE" not in str(body)


def test_concurrent_syncs_do_not_double_award() -> None:
    user, _ = ensure_contribution_ready_citizen(phone="+96170111017")
    ticket = _ticket(owner_id=user.user_id, ticket_id="tkt_conc_1", status="ASSIGNED")

    def _sync() -> None:
        rewards_service.sync_ticket(ticket)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: _sync(), range(8)))
    events = [
        event
        for event in rewards_service._ledger().list_by_citizen(user.user_id)
        if event.delta > 0
    ]
    assert len(events) == 1
    assert rewards_service.get_citizen_rewards(user.user_id).confirmed_points == 10


def test_invalid_leaderboard_query_is_rejected(anonymous_client: TestClient) -> None:
    bad_period = anonymous_client.get("/v1/rewards/leaderboard?period=weekly")
    assert bad_period.status_code == 400
    bad_cursor = anonymous_client.get("/v1/rewards/leaderboard?cursor=%%%")
    assert bad_cursor.status_code == 400

"""Dedicated duplicate-candidate and comparison endpoints (issue #269)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.database.dynamo_ticket_store import DynamoTicketStore
from app.database.memory import ticket_store
from app.main import app
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import authenticated_test_client, contribution_ready_auth_headers
from tests.test_read_tickets import create_ticket
from tests.test_submit_ticket import VALID_PAYLOAD

BEIRUT_MUNICIPALITY = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
OTHER_MUNICIPALITY = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ROAD_MAINTENANCE = "d1111111-1111-1111-1111-111111111111"

CANDIDATE_KEYS = {
    "ticketId",
    "ticketNumber",
    "status",
    "category",
    "priority",
    "summary",
    "createdAt",
    "location",
    "distanceMeters",
    "imageUrl",
    "suggested",
    "score",
    "categoryMatch",
    "mergeable",
}

COMPARISON_KEYS = {
    "ticketId",
    "ticketNumber",
    "description",
    "status",
    "category",
    "priority",
    "createdAt",
    "location",
    "imageUrl",
    "distanceMeters",
}

PRIVATE_KEYS = {
    "contact",
    "trackingCode",
    "imageObjectKey",
    "imageReferences",
    "auditHistory",
    "statusHistory",
    "ai",
    "public",
    "ownerUserId",
    "duplicateSuggestions",
}


def _override_ticket(ticket_id: str, **fields) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(stored.model_copy(update=fields))


def _candidates(client, ticket_id: str, **params):
    return client.get(f"/v1/tickets/{ticket_id}/duplicate-candidates", params=params)


def _comparison(client, ticket_id: str, candidate_id: str):
    return client.get(f"/v1/tickets/{ticket_id}/duplicate-comparison/{candidate_id}")


def _move_ticket(ticket_id: str, *, latitude: float, longitude: float) -> None:
    stored = ticket_store.get(ticket_id)
    assert stored is not None
    ticket_store.save(
        stored.model_copy(
            update={
                "location": stored.location.model_copy(
                    update={"latitude": latitude, "longitude": longitude}
                )
            }
        )
    )


def test_duplicate_candidates_return_bounded_mergeable_projection(client):
    source = create_ticket(client, "Source pothole report near the university gate.")
    candidate = create_ticket(client, "Second pothole report at the same crossing.")

    response = _candidates(client, source["ticketId"])

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 20
    item = next(row for row in body["items"] if row["ticketId"] == candidate["ticketId"])
    assert set(item) == CANDIDATE_KEYS
    assert PRIVATE_KEYS.isdisjoint(set(item))
    assert item["mergeable"] is True
    assert item["category"] == "road_damage"
    assert set(item["location"]) == {"latitude", "longitude", "addressText"}
    assert item["summary"] == "Second pothole report at the same crossing."
    # Presigned URLs only; the raw storage key must never appear in the payload.
    assert item["imageUrl"] is None or item["imageUrl"].startswith("http")


def test_duplicate_candidates_exclude_self_grouped_and_other_categories(client):
    source = create_ticket(client, "Source report for candidate filtering.")
    same_category = create_ticket(client, "Same effective category candidate.")
    other_category = create_ticket(client, "Different effective category candidate.")
    grouped = create_ticket(client, "Already grouped candidate.")
    unclassified = create_ticket(client, "Still pending classification candidate.")
    resolved = create_ticket(client, "Closed candidate that is no longer open.")

    _override_ticket(other_category["ticketId"], ai_suggested_category="waste")
    _override_ticket(grouped["ticketId"], duplicate_group_id="dup_existing")
    _override_ticket(
        unclassified["ticketId"],
        ai_suggested_category=None,
        final_category=None,
        category="PENDING_CLASSIFICATION",
    )
    _override_ticket(resolved["ticketId"], status="CLOSED")

    response = _candidates(client, source["ticketId"], limit=50)

    assert response.status_code == 200
    ids = {item["ticketId"] for item in response.json()["items"]}
    assert same_category["ticketId"] in ids
    assert source["ticketId"] not in ids
    assert other_category["ticketId"] not in ids
    assert grouped["ticketId"] not in ids
    assert unclassified["ticketId"] not in ids
    assert resolved["ticketId"] not in ids


def test_duplicate_candidates_match_reviewed_category_over_ai_suggestion(client):
    source = create_ticket(client, "Source report reviewed as waste.")
    candidate = create_ticket(client, "Candidate reviewed as waste too.")
    stale = create_ticket(client, "Candidate that only looks like waste to the AI.")

    _override_ticket(source["ticketId"], final_category="waste")
    _override_ticket(candidate["ticketId"], final_category="waste")
    _override_ticket(stale["ticketId"], final_category="road_damage", ai_suggested_category="waste")

    response = _candidates(client, source["ticketId"], limit=50)

    assert response.status_code == 200
    ids = {item["ticketId"] for item in response.json()["items"]}
    assert candidate["ticketId"] in ids
    assert stale["ticketId"] not in ids


def test_duplicate_candidates_paginate_to_candidates_beyond_the_first_page(client):
    source = create_ticket(client, "Source report for candidate pagination.")
    candidate_ids = {
        create_ticket(client, f"Paginated duplicate candidate number {index}.")["ticketId"]
        for index in range(3)
    }

    seen: set[str] = set()
    cursor: str | None = None
    for _ in range(5):
        params = {"limit": 1}
        if cursor:
            params["cursor"] = cursor
        response = _candidates(client, source["ticketId"], **params)
        assert response.status_code == 200
        body = response.json()
        page_ids = {item["ticketId"] for item in body["items"]}
        assert not page_ids.intersection(seen)
        seen.update(page_ids)
        cursor = body["nextCursor"]
        if not cursor:
            break

    assert candidate_ids.issubset(seen)
    assert source["ticketId"] not in seen


def test_duplicate_candidates_continue_past_non_matching_source_page(client):
    """A valid candidate must not be hidden by newer non-matching source rows."""
    source = create_ticket(client, "Source report that outlives filler pages.")
    candidate = create_ticket(client, "Older matching candidate behind filler rows.")

    fillers = [
        create_ticket(client, f"Newer non-matching filler ticket number {index}.")
        for index in range(3)
    ]
    for filler in fillers:
        _override_ticket(filler["ticketId"], ai_suggested_category="waste")

    response = _candidates(client, source["ticketId"], limit=1)

    assert response.status_code == 200
    ids = {item["ticketId"] for item in response.json()["items"]}
    assert candidate["ticketId"] in ids


def test_duplicate_candidates_apply_the_search_query(client):
    source = create_ticket(client, "Source report for candidate search.")
    matching = create_ticket(client, "Collapsed manhole cover on Bliss Street.")
    other = create_ticket(client, "Unrelated broken kerbstone near the corniche.")

    response = _candidates(client, source["ticketId"], q="manhole", limit=50)

    assert response.status_code == 200
    ids = {item["ticketId"] for item in response.json()["items"]}
    assert ids == {matching["ticketId"]}
    assert other["ticketId"] not in ids


def test_duplicate_candidates_flag_detector_suggestions(client):
    source = create_ticket(client, "Source report used for detector suggestions.")
    nearby = create_ticket(client, "Nearby duplicate the detector should suggest.")
    faraway = create_ticket(client, "Same category report in another town entirely.")
    _move_ticket(faraway["ticketId"], latitude=34.436, longitude=35.849)

    response = _candidates(client, source["ticketId"], limit=50)

    assert response.status_code == 200
    items = {item["ticketId"]: item for item in response.json()["items"]}
    assert items[nearby["ticketId"]]["suggested"] is True
    assert items[nearby["ticketId"]]["score"] is not None
    assert items[nearby["ticketId"]]["categoryMatch"] == "same"
    assert items[nearby["ticketId"]]["distanceMeters"] is not None
    # Still mergeable, just not surfaced by the automated detector.
    assert items[faraway["ticketId"]]["suggested"] is False
    assert items[faraway["ticketId"]]["score"] is None
    assert items[faraway["ticketId"]]["mergeable"] is True


def test_duplicate_candidates_are_empty_while_the_source_is_unclassified(client):
    source = create_ticket(client, "Source report still pending classification.")
    create_ticket(client, "Classified candidate that must not be offered.")
    _override_ticket(
        source["ticketId"],
        ai_suggested_category=None,
        final_category=None,
        category="PENDING_CLASSIFICATION",
    )

    response = _candidates(client, source["ticketId"])

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["nextCursor"] is None


def test_duplicate_candidates_respect_staff_scope(client, staff_auth_headers):
    source = create_ticket(client, "In-scope source report for scoped candidates.")
    in_scope = create_ticket(client, "In-scope candidate for municipal staff.")
    out_of_scope = create_ticket(client, "Candidate owned by another municipality.")

    for ticket_id in (source["ticketId"], in_scope["ticketId"]):
        _override_ticket(
            ticket_id,
            municipality_id=BEIRUT_MUNICIPALITY,
            department_id=ROAD_MAINTENANCE,
        )
    _override_ticket(out_of_scope["ticketId"], municipality_id=OTHER_MUNICIPALITY)

    response = client.get(
        f"/v1/tickets/{source['ticketId']}/duplicate-candidates",
        params={"limit": 50},
        headers=staff_auth_headers,
    )

    assert response.status_code == 200
    ids = {item["ticketId"] for item in response.json()["items"]}
    assert in_scope["ticketId"] in ids
    assert out_of_scope["ticketId"] not in ids


def test_duplicate_candidates_return_404_for_unknown_or_out_of_scope_source(
    client,
    staff_auth_headers,
):
    missing = _candidates(client, "tkt_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "TICKET_NOT_FOUND"

    foreign = create_ticket(client, "Source report in another municipality.")
    _override_ticket(foreign["ticketId"], municipality_id=OTHER_MUNICIPALITY)

    scoped = client.get(
        f"/v1/tickets/{foreign['ticketId']}/duplicate-candidates",
        headers=staff_auth_headers,
    )
    assert scoped.status_code == 404
    assert scoped.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_duplicate_candidates_require_staff_auth(client):
    source = create_ticket(client, "Source report that must stay staff-only.")

    response = TestClient(app).get(f"/v1/tickets/{source['ticketId']}/duplicate-candidates")

    assert response.status_code == 401


def test_duplicate_candidates_reject_an_invalid_cursor(client):
    source = create_ticket(client, "Source report for cursor validation.")

    response = _candidates(client, source["ticketId"], cursor="not-a-cursor")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "cursor" for detail in body["error"]["details"])


def test_duplicate_comparison_returns_a_bounded_projection(client):
    source = create_ticket(client, "Source report for the comparison projection.")
    candidate = create_ticket(client, "Candidate report for the comparison projection.")
    _move_ticket(candidate["ticketId"], latitude=33.896612, longitude=35.478419)

    response = _comparison(client, source["ticketId"], candidate["ticketId"])

    assert response.status_code == 200
    body = response.json()
    assert set(body) == COMPARISON_KEYS
    assert PRIVATE_KEYS.isdisjoint(set(body))
    assert body["ticketId"] == candidate["ticketId"]
    assert body["description"] == "Candidate report for the comparison projection."
    assert body["category"] == "road_damage"
    assert set(body["location"]) == {"latitude", "longitude", "addressText"}
    assert body["distanceMeters"] is not None and body["distanceMeters"] > 0


def test_duplicate_comparison_omits_private_fields_even_when_populated(client):
    source = create_ticket(client, "Source report with private data attached.")
    candidate = create_ticket(client, "Candidate report with private data attached.")

    detail = client.get(f"/v1/tickets/{candidate['ticketId']}").json()
    assert detail["contact"]["phone"]
    assert detail["trackingCode"]
    assert detail["imageObjectKey"]

    response = _comparison(client, source["ticketId"], candidate["ticketId"])

    assert response.status_code == 200
    body = response.json()
    assert PRIVATE_KEYS.isdisjoint(set(body))
    # Only a time-limited presigned URL may reference the stored object; the key
    # itself is never projected as a field callers can read or reuse.
    serialized = response.text.replace(body["imageUrl"] or "", "")
    assert detail["trackingCode"] not in serialized
    assert detail["contact"]["phone"] not in serialized
    assert detail["imageObjectKey"] not in serialized


def test_duplicate_comparison_returns_404_when_either_ticket_is_missing(client):
    source = create_ticket(client, "Source report for comparison 404s.")

    missing_candidate = _comparison(client, source["ticketId"], "tkt_missing")
    assert missing_candidate.status_code == 404
    assert missing_candidate.json()["error"]["code"] == "TICKET_NOT_FOUND"

    missing_source = _comparison(client, "tkt_missing", source["ticketId"])
    assert missing_source.status_code == 404
    assert missing_source.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_duplicate_comparison_returns_404_for_out_of_scope_tickets(client, staff_auth_headers):
    source = create_ticket(client, "In-scope source report for comparison scope.")
    foreign = create_ticket(client, "Out-of-scope candidate for comparison scope.")
    _override_ticket(
        source["ticketId"],
        municipality_id=BEIRUT_MUNICIPALITY,
        department_id=ROAD_MAINTENANCE,
    )
    _override_ticket(foreign["ticketId"], municipality_id=OTHER_MUNICIPALITY)

    response = client.get(
        f"/v1/tickets/{source['ticketId']}/duplicate-comparison/{foreign['ticketId']}",
        headers=staff_auth_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_duplicate_comparison_requires_staff_auth(client):
    source = create_ticket(client, "Source report for comparison auth.")
    candidate = create_ticket(client, "Candidate report for comparison auth.")

    response = TestClient(app).get(
        f"/v1/tickets/{source['ticketId']}/duplicate-comparison/{candidate['ticketId']}"
    )

    assert response.status_code == 401


def test_duplicate_candidates_and_comparison_work_on_moto_dynamodb(
    dynamodb_settings: Settings,
) -> None:
    store = DynamoTicketStore(dynamodb_settings)
    original_store = ticket_service._store
    ticket_service._store = store

    try:
        client = authenticated_test_client()

        def create_dynamo_ticket(description: str) -> dict:
            created = client.post(
                "/v1/tickets",
                json={**VALID_PAYLOAD, "description": description},
                headers=contribution_ready_auth_headers(),
            )
            assert created.status_code == 201, created.text
            body = created.json()
            assert ticket_service.process_ticket_ai(body["ticketId"]) is True
            return body

        source = create_dynamo_ticket("Dynamo source report for duplicate candidates.")
        candidate = create_dynamo_ticket("Dynamo candidate report for duplicate candidates.")

        page = client.get(f"/v1/tickets/{source['ticketId']}/duplicate-candidates")
        assert page.status_code == 200, page.text
        items = page.json()["items"]
        assert any(item["ticketId"] == candidate["ticketId"] for item in items)
        assert all(set(item) == CANDIDATE_KEYS for item in items)

        comparison = client.get(
            f"/v1/tickets/{source['ticketId']}/duplicate-comparison/{candidate['ticketId']}"
        )
        assert comparison.status_code == 200, comparison.text
        assert set(comparison.json()) == COMPARISON_KEYS

        paged = client.get(
            f"/v1/tickets/{source['ticketId']}/duplicate-candidates",
            params={"limit": 1},
        )
        assert paged.status_code == 200, paged.text
        assert len(paged.json()["items"]) <= 1
    finally:
        ticket_service._store = original_store

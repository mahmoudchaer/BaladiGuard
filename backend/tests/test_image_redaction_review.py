"""Staff redaction review and correction controls (issue #255)."""

from __future__ import annotations

from app.database.memory import ticket_store
from app.services.redaction.processor import ProcessingResult
from app.services.uploads.photo_upload_service import PhotoUploadService
from tests.conftest import (
    contribution_ready_auth_headers,
    ensure_contribution_ready_citizen,
    issue_test_staff_token,
)
from tests.test_staff_authorization import BEIRUT_MUNICIPALITY, OTHER_MUNICIPALITY, ROAD_MAINTENANCE
from tests.test_submit_ticket import VALID_PAYLOAD


def _submit_report(client, *, phone: str = "+96170925501") -> dict:
    ensure_contribution_ready_citizen(phone=phone, full_name="Redaction Review Citizen", email=None)
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(
            phone=phone,
            full_name="Redaction Review Citizen",
            email=None,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _auth(client, username: str = "admin") -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_test_staff_token(client, username=username)}"}


def _candidate_key(ticket_id: str, generation: int = 1) -> str:
    return (
        f"reports/redacted/v1/{PhotoUploadService.ticket_scope(ticket_id)}/"
        f"g{generation}/candidate.jpg"
    )


def _stamp_review_required(ticket_id: str, *, municipality_id: str | None = None) -> str:
    candidate = _candidate_key(ticket_id)
    update = {
        "image_redaction_status": "review_required",
        "image_redaction_generation": 1,
        "image_redaction_candidate_object_key": candidate,
        "image_redaction_candidate_revision": 1,
        "image_redaction_reason_code": "LOW_CONFIDENCE",
        "image_redaction_detector": "fake",
        "image_redaction_detector_version": "v1",
        "image_redaction_regions": [
            {
                "kind": "plate",
                "confidence": 70,
                "left": 0.2,
                "top": 0.3,
                "width": 0.4,
                "height": 0.2,
            }
        ],
    }
    if municipality_id is not None:
        stored = ticket_store.get(ticket_id)
        assert stored is not None
        ticket_store.save(
            stored.model_copy(
                update={
                    "municipality_id": municipality_id,
                    "department_id": ROAD_MAINTENANCE,
                }
            )
        )
    patched = ticket_store.patch_fields(ticket_id, update)
    assert patched is not None
    return candidate


def test_review_payload_is_staff_only_and_omits_storage_keys(anonymous_client, monkeypatch):
    created = _submit_report(anonymous_client)
    candidate = _stamp_review_required(created["ticketId"])
    endpoint = f"/v1/tickets/{created['ticketId']}/image-redaction/review"
    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/{key}",
    )

    assert anonymous_client.get(endpoint).status_code == 401

    response = anonymous_client.get(endpoint, headers=_auth(anonymous_client))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "review_required"
    assert body["originalImageUrl"].startswith("https://example.test/")
    assert body["candidateImageUrl"] == f"https://example.test/{candidate}"
    assert body["canApprove"] is True
    assert body["canReject"] is True
    assert body["canAddManualRegions"] is True
    assert body["candidateRevision"] == 1
    serialized = response.text
    assert "imageObjectKey" not in serialized
    assert "reports/" not in serialized.replace(body["originalImageUrl"], "").replace(
        body["candidateImageUrl"], ""
    )


def test_out_of_scope_staff_cannot_view_or_decide(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925502")
    _stamp_review_required(created["ticketId"], municipality_id=OTHER_MUNICIPALITY)
    headers = _auth(anonymous_client, username="staff")
    ticket_id = created["ticketId"]
    for method, path in (
        ("get", f"/v1/tickets/{ticket_id}/image-redaction/review"),
        ("post", f"/v1/tickets/{ticket_id}/image-redaction/approve"),
        ("post", f"/v1/tickets/{ticket_id}/image-redaction/reject"),
        ("post", f"/v1/tickets/{ticket_id}/image-redaction/manual-regions"),
    ):
        kwargs = {"headers": headers}
        if method == "post":
            kwargs["json"] = {
                "expectedGeneration": 1,
                "expectedCandidateRevision": 1,
                "regions": [],
            }
        response = getattr(anonymous_client, method)(path, **kwargs)
        assert response.status_code == 404, path
        assert "originalImageUrl" not in response.text
        assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_approve_exposes_derivative_and_records_audit(anonymous_client, monkeypatch):
    created = _submit_report(anonymous_client, phone="+96170925503")
    candidate = _stamp_review_required(created["ticketId"], municipality_id=BEIRUT_MUNICIPALITY)
    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/{key}",
    )
    headers = _auth(anonymous_client)
    approved = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "completed"
    assert body["publicImageReady"] is True

    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.public_image_object_key == candidate
    assert stored.image_redaction_status == "completed"

    ticket = anonymous_client.get(f"/v1/tickets/{created['ticketId']}", headers=headers)
    assert ticket.status_code == 200
    actions = [entry["actionType"] for entry in ticket.json().get("auditHistory", [])]
    assert "IMAGE_REDACTION_APPROVE" in actions
    actors = [
        entry
        for entry in ticket.json()["auditHistory"]
        if entry["actionType"] == "IMAGE_REDACTION_APPROVE"
    ]
    assert actors[0]["actorId"]
    assert actors[0]["actorRole"] == "administrator"
    assert actors[0]["newValue"] == "completed:g1:fake:v1"


def test_reject_keeps_image_private_only(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925504")
    _stamp_review_required(created["ticketId"])
    headers = _auth(anonymous_client)
    rejected = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/reject",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=headers,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "private_only"
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.public_image_object_key is None
    assert stored.image_redaction_status == "private_only"


def test_public_clients_stay_fail_closed_until_approval(anonymous_client, monkeypatch):
    created = _submit_report(anonymous_client, phone="+96170925505")
    _stamp_review_required(created["ticketId"])
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    ticket_store.patch_fields(
        created["ticketId"],
        {
            "final_category": "road_damage",
            "public_status": "PUBLISHED",
            "public_description": "Road hazard",
            "public_location_label": "Hamra",
            "public_published_at": stored.created_at,
        },
    )
    public = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert public.status_code == 200
    assert public.json()["photoUrl"] is None
    assert stored.image_object_key not in public.text

    anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=_auth(anonymous_client),
    )
    monkeypatch.setattr(
        "app.services.complaints.ticket_read_mapper.build_image_url",
        lambda key: f"https://example.test/{key}",
    )
    after = anonymous_client.get(f"/v1/tickets/public/{created['ticketNumber']}")
    assert after.json()["photoUrl"].startswith("https://example.test/reports/redacted/")


def test_concurrent_decisions_do_not_silently_overwrite(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925506")
    _stamp_review_required(created["ticketId"])
    headers = _auth(anonymous_client)
    first = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=headers,
    )
    second = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/reject",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "REDACTION_REVIEW_CONFLICT"
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.image_redaction_status == "completed"


def test_stale_generation_is_rejected(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925507")
    _stamp_review_required(created["ticketId"])
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 9, "expectedCandidateRevision": 1},
        headers=_auth(anonymous_client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REDACTION_REVIEW_CONFLICT"


def test_manual_regions_generate_new_candidate_without_editing_original(
    anonymous_client, monkeypatch
):
    created = _submit_report(anonymous_client, phone="+96170925508")
    original_key = ticket_store.get(created["ticketId"]).image_object_key
    _stamp_review_required(created["ticketId"])
    new_key = _candidate_key(created["ticketId"]) + ".manual"

    class ManualProcessor:
        def apply_manual_regions(self, **kwargs):
            assert kwargs["source_key"] == original_key
            return ProcessingResult(
                status="review_required",
                derivative_key=new_key,
                source_fingerprint="abc",
                detector="staff-manual",
                detector_version="v1",
                face_count=0,
                plate_count=1,
                minimum_confidence=70,
                reason_code="MANUAL_CORRECTION",
                regions=(
                    {
                        "kind": "plate",
                        "confidence": 70,
                        "left": 0.2,
                        "top": 0.3,
                        "width": 0.4,
                        "height": 0.2,
                    },
                    {
                        "kind": "manual",
                        "confidence": 100,
                        "left": 0.05,
                        "top": 0.05,
                        "width": 0.1,
                        "height": 0.1,
                    },
                ),
            )

    monkeypatch.setattr(
        "app.services.redaction.queue.image_redaction_queue.processor",
        ManualProcessor(),
    )
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.05, "top": 0.05, "width": 0.1, "height": 0.1}],
        },
        headers=_auth(anonymous_client),
    )
    assert response.status_code == 200, response.text
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.image_object_key == original_key
    assert stored.image_redaction_candidate_object_key == new_key
    assert stored.public_image_object_key is None
    assert stored.image_redaction_status == "review_required"
    kinds = [
        region.kind if hasattr(region, "kind") else region["kind"]
        for region in stored.image_redaction_regions
    ]
    assert "manual" in kinds


def test_invalid_manual_region_is_rejected(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925509")
    _stamp_review_required(created["ticketId"])
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.1, "top": 0.1, "width": 0, "height": 0.2}],
        },
        headers=_auth(anonymous_client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    stored = ticket_store.get(created["ticketId"])
    assert stored.image_redaction_candidate_object_key == _candidate_key(created["ticketId"])


def test_overflowing_manual_region_is_rejected(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925511")
    _stamp_review_required(created["ticketId"])
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.9, "top": 0.1, "width": 0.5, "height": 0.2}],
        },
        headers=_auth(anonymous_client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_manual_correction_then_stale_approve_keeps_new_candidate(anonymous_client, monkeypatch):
    created = _submit_report(anonymous_client, phone="+96170925512")
    original_candidate = _stamp_review_required(created["ticketId"])
    new_key = original_candidate + ".manual"

    class ManualProcessor:
        def apply_manual_regions(self, **_kwargs):
            return ProcessingResult(
                status="review_required",
                derivative_key=new_key,
                source_fingerprint="abc",
                detector="staff-manual",
                detector_version="v1",
                face_count=0,
                plate_count=1,
                minimum_confidence=70,
                reason_code="MANUAL_CORRECTION",
                regions=(),
            )

    monkeypatch.setattr(
        "app.services.redaction.queue.image_redaction_queue.processor",
        ManualProcessor(),
    )
    headers = _auth(anonymous_client)
    manual = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.1, "top": 0.1, "width": 0.2, "height": 0.2}],
        },
        headers=headers,
    )
    assert manual.status_code == 200, manual.text
    stale_approve = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=headers,
    )
    assert stale_approve.status_code == 409
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.image_redaction_candidate_object_key == new_key
    assert stored.public_image_object_key is None
    assert stored.image_redaction_candidate_revision == 2


def test_second_manual_correction_loses_to_newer_revision(anonymous_client, monkeypatch):
    created = _submit_report(anonymous_client, phone="+96170925513")
    original_candidate = _stamp_review_required(created["ticketId"])
    keys = {"n": 0}

    class ManualProcessor:
        def apply_manual_regions(self, **_kwargs):
            keys["n"] += 1
            return ProcessingResult(
                status="review_required",
                derivative_key=f"{original_candidate}.manual{keys['n']}",
                source_fingerprint="abc",
                detector="staff-manual",
                detector_version="v1",
                face_count=0,
                plate_count=1,
                minimum_confidence=70,
                reason_code="MANUAL_CORRECTION",
                regions=(),
            )

    monkeypatch.setattr(
        "app.services.redaction.queue.image_redaction_queue.processor",
        ManualProcessor(),
    )
    headers = _auth(anonymous_client)
    first = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.1, "top": 0.1, "width": 0.2, "height": 0.2}],
        },
        headers=headers,
    )
    second = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/manual-regions",
        json={
            "expectedGeneration": 1,
            "expectedCandidateRevision": 1,
            "regions": [{"left": 0.2, "top": 0.2, "width": 0.2, "height": 0.2}],
        },
        headers=headers,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409
    stored = ticket_store.get(created["ticketId"])
    assert stored is not None
    assert stored.image_redaction_candidate_object_key == f"{original_candidate}.manual1"
    assert stored.image_redaction_candidate_revision == 2


def test_failed_status_cannot_be_approved(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925510")
    ticket_store.patch_fields(
        created["ticketId"],
        {"image_redaction_status": "failed", "image_redaction_reason_code": "ORIGINAL_READ_FAILED"},
    )
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/approve",
        json={"expectedGeneration": 1, "expectedCandidateRevision": 1},
        headers=_auth(anonymous_client),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REDACTION_NOT_READY"


def test_reprocess_audit_records_processor_version(anonymous_client):
    created = _submit_report(anonymous_client, phone="+96170925514")
    _stamp_review_required(created["ticketId"])
    headers = _auth(anonymous_client)
    response = anonymous_client.post(
        f"/v1/tickets/{created['ticketId']}/image-redaction/reprocess",
        headers=headers,
    )
    assert response.status_code == 202, response.text
    ticket = anonymous_client.get(f"/v1/tickets/{created['ticketId']}", headers=headers)
    entries = [
        entry
        for entry in ticket.json()["auditHistory"]
        if entry["actionType"] == "IMAGE_REDACTION_REPROCESS"
    ]
    assert entries
    assert "fake:v1" in entries[0]["previousValue"]
    assert "g2" in entries[0]["newValue"]

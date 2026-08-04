from tests.test_read_tickets import create_ticket

ADMIN_STAFF_ID = "staff_admin_001"


def test_update_ticket_status_moves_through_allowed_workflow(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff-1", "note": "Queued for review."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UNDER_REVIEW"
    assert body["updatedBy"] == ADMIN_STAFF_ID
    assert body["updatedAt"] == body["statusHistory"][-1]["changedAt"]
    assert body["statusHistory"] == [
        {
            "status": "SUBMITTED",
            "changedAt": created["createdAt"],
            "changedBy": None,
            "note": "Ticket submitted.",
        },
        {
            "status": "UNDER_REVIEW",
            "changedAt": body["updatedAt"],
            "changedBy": ADMIN_STAFF_ID,
            "note": "Queued for review.",
        },
    ]


def test_update_ticket_status_rejects_invalid_transition(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "RESOLVED"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_STATUS_TRANSITION"
    assert "Cannot move ticket from Submitted to Resolved" in body["error"]["message"]


def test_update_ticket_status_rejects_unknown_status_value(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "DONE"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(detail["field"] == "status" for detail in body["error"]["details"])


def test_update_ticket_status_returns_404_for_unknown_ticket(client):
    response = client.patch(
        "/v1/tickets/tkt_missing/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_update_ticket_status_closes_from_submitted(client):
    created = create_ticket(client)

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED", "updatedBy": "staff-2", "note": "Duplicate report."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CLOSED"
    assert body["statusHistory"][-1]["status"] == "CLOSED"


def test_update_ticket_status_emits_resolved_event_for_closed(client, monkeypatch):
    created = create_ticket(client)
    emitted: list[dict[str, str]] = []

    def capture(**kwargs):
        emitted.append(kwargs)

    monkeypatch.setattr(
        "app.services.complaints.ticket_service.ticket_service._emit_notification_safe",
        capture,
    )

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED"},
    )

    assert response.status_code == 200
    assert emitted
    assert emitted[-1]["event"] == "ticket_resolved"
    assert emitted[-1]["status"] == "CLOSED"


def test_update_ticket_status_rejects_transition_from_closed(client):
    created = create_ticket(client)
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "CLOSED"},
    )

    response = client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


def test_get_ticket_includes_status_history_after_updates(client):
    created = create_ticket(client)
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW", "updatedBy": "staff-1"},
    )
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "ASSIGNED", "updatedBy": "staff-2"},
    )

    response = client.get(f"/v1/tickets/{created['ticketId']}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ASSIGNED"
    assert [entry["status"] for entry in body["statusHistory"]] == [
        "SUBMITTED",
        "UNDER_REVIEW",
        "ASSIGNED",
    ]
    assert body["statusHistory"][1]["changedBy"] == ADMIN_STAFF_ID
    assert body["statusHistory"][2]["changedBy"] == ADMIN_STAFF_ID


def test_list_tickets_includes_status_history(client):
    created = create_ticket(
        client,
        description="Overflowing garbage bins blocking the sidewalk and attracting pests.",
    )
    client.patch(
        f"/v1/tickets/{created['ticketId']}/status",
        json={"status": "UNDER_REVIEW"},
    )

    response = client.get("/v1/tickets")

    assert response.status_code == 200
    ticket = next(item for item in response.json() if item["ticketId"] == created["ticketId"])
    assert len(ticket["statusHistory"]) == 2
    assert ticket["statusHistory"][0]["status"] == "SUBMITTED"

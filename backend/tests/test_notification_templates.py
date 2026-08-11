from app.services.notifications import (
    render_notification,
    render_ticket_created,
    render_ticket_resolved,
    render_ticket_updated,
    status_text_for,
)


def test_status_text_for_known_statuses():
    assert status_text_for("SUBMITTED") == "Submitted"
    assert status_text_for("UNDER_REVIEW") == "Under Review"
    assert status_text_for("RESOLVED") == "Resolved"


def test_render_ticket_created_includes_ticket_number_and_status_text():
    message = render_ticket_created(
        ticket_id="tkt_abc123",
        ticket_number="BG-2026-0042",
        tracking_code="ZX98YU",
    )

    assert message.event == "ticket_created"
    assert message.ticket_id == "tkt_abc123"
    assert message.status == "SUBMITTED"
    assert message.status_text == "Submitted"
    assert "tkt_abc123" not in message.body
    assert "BG-2026-0042" in message.body
    assert "Status: Submitted." in message.body
    assert "Tracking code: ZX98YU." in message.body
    assert "created" in message.subject.lower()


def test_render_ticket_updated_includes_reference_and_status_text():
    message = render_ticket_updated(
        ticket_id="tkt_abc123",
        status="IN_PROGRESS",
        ticket_number="BG-2026-0042",
    )

    assert message.event == "ticket_updated"
    assert message.ticket_id == "tkt_abc123"
    assert message.status == "IN_PROGRESS"
    assert message.status_text == "In Progress"
    assert "tkt_abc123" not in message.body
    assert "Status: In Progress." in message.body
    assert "updated" in message.subject.lower()


def test_render_ticket_resolved_includes_reference_and_status_text():
    message = render_ticket_resolved(
        ticket_id="tkt_abc123",
        ticket_number="BG-2026-0042",
        tracking_code="ZX98YU",
    )

    assert message.event == "ticket_resolved"
    assert message.ticket_id == "tkt_abc123"
    assert message.status == "RESOLVED"
    assert message.status_text == "Resolved"
    assert "tkt_abc123" not in message.body
    assert "Status: Resolved." in message.body
    assert "resolved" in message.subject.lower()


def test_render_notification_dispatches_by_event():
    created = render_notification(
        "ticket_created",
        ticket_id="tkt_1",
        status="SUBMITTED",
    )
    updated = render_notification(
        "ticket_updated",
        ticket_id="tkt_1",
        status="ASSIGNED",
    )
    resolved = render_notification(
        "ticket_resolved",
        ticket_id="tkt_1",
        status="RESOLVED",
    )

    assert created.event == "ticket_created"
    assert updated.event == "ticket_updated"
    assert updated.status_text == "Assigned"
    assert resolved.event == "ticket_resolved"


def test_render_ticket_created_requires_ticket_id():
    try:
        render_ticket_created(ticket_id="   ")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "ticket_id" in str(exc)


def test_unknown_status_fails_closed_for_all_events():
    cases = [
        lambda: render_ticket_created(ticket_id="tkt_1", status="NOT_A_STATUS"),
        lambda: render_ticket_updated(ticket_id="tkt_1", status="NOT_A_STATUS"),
        lambda: render_ticket_resolved(ticket_id="tkt_1", status="NOT_A_STATUS"),
    ]
    for renderer in cases:
        try:
            renderer()
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "Unknown ticket status" in str(exc)


def test_ticket_updated_rejects_terminal_statuses():
    for status in ("RESOLVED", "CLOSED"):
        try:
            render_ticket_updated(ticket_id="tkt_1", status=status)
            raise AssertionError(f"expected ValueError for {status}")
        except ValueError as exc:
            assert "ticket_resolved" in str(exc)


def test_ticket_resolved_rejects_non_terminal_statuses():
    try:
        render_ticket_resolved(ticket_id="tkt_1", status="IN_PROGRESS")
        raise AssertionError("expected ValueError")
    except ValueError as exp:
        assert "RESOLVED or CLOSED" in str(exp)


def test_render_ticket_resolved_closed_uses_closed_wording():
    message = render_ticket_resolved(ticket_id="tkt_abc123", status="CLOSED")

    assert message.event == "ticket_resolved"
    assert message.status == "CLOSED"
    assert message.status_text == "Closed"
    assert "was closed." in message.body
    assert "Status: Closed." in message.body
    assert "closed" in message.subject.lower()
    assert "resolved" not in message.body.lower()


def test_notification_message_as_dict_includes_required_fields():
    message = render_ticket_updated(ticket_id="tkt_abc123", status="UNDER_REVIEW")
    payload = message.as_dict()

    assert payload["ticketId"] == "tkt_abc123"
    assert payload["status"] == "UNDER_REVIEW"
    assert payload["statusText"] == "Under Review"
    assert payload["event"] == "ticket_updated"
    assert "body" in payload
    assert "subject" in payload

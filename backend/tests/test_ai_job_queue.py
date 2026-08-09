from app.config import Settings
from app.database.dynamo_ai_job_store import DynamoAiJobStore
from app.database.memory import ticket_store
from app.database.memory_ai_job import InMemoryAiJobStore, ai_job_id
from app.schemas.ticket import ReportContact, SubmitTicketRequest
from app.services.ai_job_queue import AiJobQueue
from app.services.ai_job_queue import ai_job_queue as api_ai_job_queue
from app.services.complaints.ticket_service import ticket_service
from tests.conftest import contribution_ready_auth_headers
from tests.test_submit_ticket import EXPECTED_CONTACT, VALID_PAYLOAD


def _submit() -> str:
    response = ticket_service.submit_ticket(
        SubmitTicketRequest.model_validate(VALID_PAYLOAD),
        owner_user_id="usr_queue_test",
        contact=ReportContact.model_validate(EXPECTED_CONTACT),
    )
    return response.ticket_id


def _queue(store: InMemoryAiJobStore | None = None) -> AiJobQueue:
    return AiJobQueue(store or InMemoryAiJobStore(), ticket_store, ticket_service)


def test_enqueue_is_durable_and_idempotent():
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()

    first = queue.enqueue(ticket_id, now=100)
    second = queue.enqueue(ticket_id, now=200)

    assert first.job_id == ai_job_id(ticket_id)
    assert second == first
    assert len(store.list()) == 1


def test_duplicate_delivery_does_not_reapply_ai(monkeypatch):
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()
    calls = 0
    original = ticket_service.process_ticket_ai

    def counted(ticket_id: str, **kwargs: object) -> bool:
        nonlocal calls
        calls += 1
        return original(ticket_id, **kwargs)

    monkeypatch.setattr(ticket_service, "process_ticket_ai", counted)
    job = queue.enqueue(ticket_id, now=100)
    assert queue.run_once(now=100).outcome == "succeeded"
    assert calls == 1

    # Simulate duplicate queue delivery after the ticket has a terminal result.
    store._jobs[job.job_id] = store.get(job.job_id).model_copy(  # type: ignore[union-attr]
        update={"status": "queued", "available_at": 101}
    )
    assert queue.run_once(now=101).outcome == "succeeded"
    assert calls == 1


def test_transient_failure_retries_with_bounded_exponential_backoff(monkeypatch):
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()
    queue.enqueue(ticket_id, now=100)

    def timeout(_ticket_id: str, **_: object) -> bool:
        raise TimeoutError

    monkeypatch.setattr(ticket_service, "process_ticket_ai", timeout)

    result = queue.run_once(now=100)

    assert result.outcome == "retried"
    job = store.get(ai_job_id(ticket_id))
    assert job is not None
    assert job.status == "queued"
    assert job.attempts == 1
    assert job.available_at > 100
    assert "TimeoutError" in (job.last_error or "")
    assert ticket_store.get(ticket_id).ai_processing_status == "pending"  # type: ignore[union-attr]


def test_attempts_exhaust_to_operator_visible_dead_letter(monkeypatch):
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()
    job = queue.enqueue(ticket_id, now=100)
    monkeypatch.setattr(ticket_service, "process_ticket_ai", lambda _ticket_id, **_: False)
    from app.config import get_settings

    settings = get_settings()
    for attempt in range(settings.ai_job_max_attempts):
        current = store.get(job.job_id)
        assert current is not None
        outcome = queue.run_once(now=current.available_at).outcome
        if attempt < settings.ai_job_max_attempts - 1:
            assert outcome == "retried"

    dead = store.get(job.job_id)
    assert dead is not None
    assert dead.status == "dead_lettered"
    assert dead.last_error


def test_stale_claim_recovery_and_manual_replay(monkeypatch):
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()
    job = queue.enqueue(ticket_id, now=100)
    claimed = store.claim_next(now=100, claim_ttl_seconds=5)
    assert claimed is not None
    ticket_store.claim_ai_processing(ticket_id, "1970-01-01T00:01:40Z")

    assert queue.recover_stale(now=106) == 1
    assert store.get(job.job_id).status == "queued"  # type: ignore[union-attr]
    assert ticket_store.get(ticket_id).ai_processing_status == "pending"  # type: ignore[union-attr]

    claimed = store.claim_next(now=106, claim_ttl_seconds=5)
    assert claimed and claimed.claim_token
    store.dead_letter(job.job_id, claimed.claim_token, now=106, reason="Permanent failure.")
    assert queue.replay(job.job_id, now=107) is True
    replayed = store.get(job.job_id)
    assert replayed is not None
    assert replayed.status == "queued"
    assert replayed.attempts == 0


def test_reconcile_recovers_ticket_saved_before_enqueue():
    store = InMemoryAiJobStore()
    queue = _queue(store)
    ticket_id = _submit()

    assert queue.reconcile(now=100) == 1
    assert store.get(ai_job_id(ticket_id)) is not None


def test_dynamo_job_claim_retry_stale_recovery_and_replay(dynamodb_settings: Settings):
    store = DynamoAiJobStore(dynamodb_settings)
    job = store.enqueue("tkt_dynamo_job", 100)
    assert store.enqueue("tkt_dynamo_job", 101).job_id == job.job_id

    claim = store.claim_next(now=100, claim_ttl_seconds=5)
    assert claim is not None and claim.claim_token
    assert store.claim_next(now=100, claim_ttl_seconds=5) is None
    assert store.retry(
        job.job_id,
        claim.claim_token,
        available_at=110,
        now=101,
        reason="TimeoutError",
    )
    assert store.claim_next(now=109, claim_ttl_seconds=5) is None

    claim = store.claim_next(now=110, claim_ttl_seconds=5)
    assert claim is not None and claim.claim_token
    assert len(store.recover_stale(now=116)) == 1
    claim = store.claim_next(now=116, claim_ttl_seconds=5)
    assert claim is not None and claim.claim_token
    assert store.dead_letter(
        job.job_id,
        claim.claim_token,
        now=116,
        reason="Permanent failure.",
    )
    assert store.replay(job.job_id, now=117) is not None
    assert store.get(job.job_id).status == "queued"  # type: ignore[union-attr]


def test_api_does_not_report_success_when_durable_enqueue_fails(client, monkeypatch):
    def fail_enqueue(*_: object, **__: object) -> None:
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(api_ai_job_queue, "enqueue", fail_enqueue)
    response = client.post(
        "/v1/tickets",
        json=VALID_PAYLOAD,
        headers=contribution_ready_auth_headers(),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_SCHEDULING_FAILED"
    assert len(ticket_store.list()) == 1

"""Pre-body upload abuse protection (issue #186 review follow-up)."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.rate_limit import clear_rate_limiter_cache
from app.core.upload_abuse import (
    MAX_UPLOAD_REQUEST_BYTES,
    reject_upload_abuse_early,
)
from app.services.uploads.photo_upload_service import (
    MAX_IMAGE_SIZE_BYTES,
    photo_upload_service,
)
from tests.conftest import contribution_ready_auth_headers


def _request(
    *,
    path: str = "/v1/uploads/report-photo",
    method: str = "POST",
    headers: dict[str, str] | None = None,
    client_host: str = "203.0.113.40",
):
    return SimpleNamespace(
        method=method,
        url=SimpleNamespace(path=path),
        headers=headers or {},
        client=SimpleNamespace(host=client_host),
        state=SimpleNamespace(request_id="req_upload_abuse"),
    )


def test_reject_upload_abuse_early_ignores_non_upload_routes() -> None:
    request = _request(path="/v1/tickets")
    assert reject_upload_abuse_early(request) is None


def test_reject_upload_abuse_early_blocks_oversized_content_length() -> None:
    request = _request(
        headers={"content-length": str(MAX_UPLOAD_REQUEST_BYTES + 1)},
    )
    response = reject_upload_abuse_early(request)
    assert response is not None
    assert response.status_code == 400
    assert response.body  # serialized before any multipart parse
    assert b"FILE_TOO_LARGE" in response.body


def test_reject_upload_abuse_early_rate_limits_without_body(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    request = _request(headers={"content-length": "128"})
    assert reject_upload_abuse_early(request) is None
    limited = reject_upload_abuse_early(request)
    assert limited is not None
    assert limited.status_code == 429
    assert b"RATE_LIMIT_EXCEEDED" in limited.body
    assert limited.headers["Retry-After"]

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_http_oversized_upload_rejected_before_service(
    anonymous_client: TestClient,
    monkeypatch,
) -> None:
    service_calls: list[str] = []

    async def tracking_upload(file, **kwargs) -> str:  # type: ignore[no-untyped-def]
        service_calls.append("called")
        return "reports/photos/should-not-happen.jpg"

    monkeypatch.setattr(photo_upload_service, "upload_report_photo", tracking_upload)

    oversized = BytesIO(b"x" * (MAX_IMAGE_SIZE_BYTES + (300 * 1024)))
    response = anonymous_client.post(
        "/v1/uploads/report-photo",
        files={"file": ("huge.jpg", oversized, "image/jpeg")},
        headers=contribution_ready_auth_headers(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert service_calls == []


def test_http_rate_limited_upload_does_not_reach_service(
    anonymous_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_LIMIT", "1")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    clear_rate_limiter_cache()

    service_calls: list[str] = []

    async def tracking_upload(file, **kwargs) -> str:  # type: ignore[no-untyped-def]
        service_calls.append("called")
        return "reports/photos/ok.jpg"

    monkeypatch.setattr(photo_upload_service, "upload_report_photo", tracking_upload)
    headers = contribution_ready_auth_headers()

    first = anonymous_client.post(
        "/v1/uploads/report-photo",
        files={"file": ("a.jpg", BytesIO(b"image-bytes"), "image/jpeg")},
        headers=headers,
    )
    second = anonymous_client.post(
        "/v1/uploads/report-photo",
        files={"file": ("b.jpg", BytesIO(b"image-bytes"), "image/jpeg")},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert 1 <= int(second.headers["Retry-After"]) <= 60
    # Second request must not reach upload processing / body handling.
    assert service_calls == ["called"]

    get_settings.cache_clear()
    clear_rate_limiter_cache()


def test_http_repeated_oversized_uploads_stay_rejected_without_service(
    anonymous_client: TestClient,
    monkeypatch,
) -> None:
    service_calls: list[str] = []

    async def tracking_upload(file, **kwargs) -> str:  # type: ignore[no-untyped-def]
        service_calls.append("called")
        return "reports/photos/nope.jpg"

    monkeypatch.setattr(photo_upload_service, "upload_report_photo", tracking_upload)

    payload = BytesIO(b"x" * (MAX_UPLOAD_REQUEST_BYTES + 1))
    for _ in range(3):
        payload.seek(0)
        response = anonymous_client.post(
            "/v1/uploads/report-photo",
            files={"file": ("huge.jpg", payload, "image/jpeg")},
            headers=contribution_ready_auth_headers(),
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"

    assert service_calls == []

"""Bounded concurrent HTTP harness for capacity validation (issue #191).

Light load only — not a distributed fleet. Synthetic traffic against a running
API (local, staging-equivalent, or dedicated staging). Never produce real
citizen data; use disposable capacitytest* identities only.

Scenarios exercise **write** paths required by the #191 workload model:
submit, photo upload, staff mutations, OTP request, and AI-queue observation
via readiness — in addition to read/smoke probes.

Examples:

  PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py --scenario smoke
  PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py \\
    --base-url https://api.staging.example --scenario write-mixed --concurrency 8 \\
    --duration-seconds 45 --staff-user admin --staff-password \"$STAFF_PASSWORD\" \\
    --citizen-token \"$CITIZEN_TOKEN\" \\
    --output ../../infra/capacity/evidence/staging-capacity-run.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

# Minimal JPEG so POST /v1/uploads/report-photo accepts the bytes.
_MIN_JPEG = bytes(
    [
        0xFF,
        0xD8,
        0xFF,
        0xE0,
        0x00,
        0x10,
        0x4A,
        0x46,
        0x49,
        0x46,
        0x00,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0xFF,
        0xDB,
        0x00,
        0x43,
        0x00,
        *([0x08] * 64),
        0xFF,
        0xC0,
        0x00,
        0x0B,
        0x08,
        0x00,
        0x01,
        0x00,
        0x01,
        0x01,
        0x01,
        0x11,
        0x00,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x08,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x10,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFF,
        0xDA,
        0x00,
        0x08,
        0x01,
        0x01,
        0x00,
        0x00,
        0x3F,
        0x00,
        0x7F,
        0xFF,
        0xD9,
    ]
)

SCENARIOS = (
    "smoke",
    "mixed",
    "submit-race",
    "upload-race",
    "staff-race",
    "staff-mutate",
    "write-mixed",
    "otp-race",
)


@dataclass
class RequestResult:
    name: str
    status: int | None
    latency_ms: float
    error: str | None = None
    body: bytes | None = None


@dataclass
class ScenarioSummary:
    scenario: str
    base_url: str
    concurrency: int
    duration_seconds: float
    total: int = 0
    ok_2xx: int = 0
    client_4xx: int = 0
    rate_limited_429: int = 0
    server_5xx: int = 0
    transport_errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    by_name: dict[str, dict[str, Any]] = field(default_factory=dict)
    ai_queue_samples: list[dict[str, Any]] = field(default_factory=list)
    created_ticket_ids: list[str] = field(default_factory=list)
    uploaded_object_keys: list[str] = field(default_factory=list)

    def record(self, result: RequestResult) -> None:
        self.total += 1
        self.latencies_ms.append(result.latency_ms)
        bucket = self.by_name.setdefault(
            result.name,
            {"count": 0, "latencies_ms": [], "status_counts": {}},
        )
        bucket["count"] += 1
        bucket["latencies_ms"].append(result.latency_ms)
        key = str(result.status if result.status is not None else result.error or "error")
        bucket["status_counts"][key] = bucket["status_counts"].get(key, 0) + 1
        if result.error and result.status is None:
            self.transport_errors += 1
            return
        status = result.status or 0
        if 200 <= status < 300:
            self.ok_2xx += 1
        elif status == 429:
            self.rate_limited_429 += 1
            self.client_4xx += 1
        elif 400 <= status < 500:
            self.client_4xx += 1
        elif status >= 500:
            self.server_5xx += 1

        if result.body and result.status is not None and 200 <= result.status < 300:
            self._ingest_success_body(result.name, result.body)

    def _ingest_success_body(self, name: str, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        if name in {"ticket_submit", "ticket_submit_from_upload"} and payload.get("ticketId"):
            self.created_ticket_ids.append(str(payload["ticketId"]))
        if name == "photo_upload" and payload.get("imageObjectKey"):
            self.uploaded_object_keys.append(str(payload["imageObjectKey"]))
        if name == "health_ready_ai":
            ai = payload.get("aiQueue") or payload.get("ai") or {}
            if isinstance(ai, dict):
                sample = {
                    "at": _iso_now(),
                    "pending": ai.get("pending"),
                    "processing": ai.get("processing"),
                    "failed": ai.get("failed"),
                    "status": ai.get("status"),
                    "source": ai.get("source"),
                }
                self.ai_queue_samples.append(sample)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 45.0,
) -> RequestResult:
    started = time.perf_counter()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    name = "request"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            latency = (time.perf_counter() - started) * 1000.0
            return RequestResult(
                name=name, status=response.status, latency_ms=latency, error=None, body=data
            )
    except urllib.error.HTTPError as exc:
        try:
            data = exc.read()
        except Exception:
            data = b""
        latency = (time.perf_counter() - started) * 1000.0
        return RequestResult(name=name, status=exc.code, latency_ms=latency, error=None, body=data)
    except Exception as exc:  # noqa: BLE001 - harness boundary
        latency = (time.perf_counter() - started) * 1000.0
        return RequestResult(
            name=name, status=None, latency_ms=latency, error=type(exc).__name__, body=None
        )


def _multipart_body(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----BaladiGuardCapacity{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
        )
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _unique_phone(worker: int, counter: int) -> str:
    # Lebanese E.164 synthetic mobiles (+961 70 + 6 digits). Disposable only.
    suffix = (worker * 10_000 + counter) % 1_000_000
    return f"+96170{suffix:06d}"


def _submit_payload(image_key: str, worker: int, counter: int) -> bytes:
    body = {
        "description": (
            f"Capacity harness synthetic report worker={worker} n={counter} "
            f"id={uuid.uuid4().hex[:12]} large pothole near AUB gate traffic risk."
        ),
        "languageHint": "auto",
        "location": {
            "latitude": 33.896112 + (counter % 50) * 0.00001,
            "longitude": 35.478419 + (worker % 20) * 0.00001,
            "addressText": f"Capacity test near AUB Main Gate {worker}-{counter}",
            "source": "GPS",
        },
        "imageObjectKey": image_key,
        "clientMetadata": {
            "platform": "capacity-harness",
            "appVersion": "0.0-capacity",
        },
    }
    return json.dumps(body).encode("utf-8")


@dataclass
class HarnessContext:
    staff_headers: dict[str, str] | None
    citizen_headers: dict[str, str] | None
    ticket_ids: list[str]
    seed_image_object_key: str
    shared_headers: dict[str, str]


def _worker_loop(
    *,
    base_url: str,
    scenario: str,
    stop_at: float,
    worker_id: int,
    ctx: HarnessContext,
) -> list[RequestResult]:
    results: list[RequestResult] = []
    counter = 0
    while time.perf_counter() < stop_at:
        counter += 1
        results.append(
            _perform_call(
                base_url=base_url,
                scenario=scenario,
                counter=counter,
                worker_id=worker_id,
                ctx=ctx,
            )
        )
    return results


def _perform_call(
    *,
    base_url: str,
    scenario: str,
    counter: int,
    worker_id: int,
    ctx: HarnessContext,
) -> RequestResult:
    name, method, path, extra_headers, payload, content_type = _pick_call(
        scenario,
        counter,
        worker_id=worker_id,
        ctx=ctx,
    )
    headers = {**ctx.shared_headers, **(extra_headers or {})}
    if content_type and payload is not None:
        headers["Content-Type"] = content_type
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    result = _request(method, url, headers=headers, body=payload)
    return RequestResult(
        name=name,
        status=result.status,
        latency_ms=result.latency_ms,
        error=result.error,
        body=result.body,
    )


def _pick_call(
    scenario: str,
    counter: int,
    *,
    worker_id: int,
    ctx: HarnessContext,
) -> tuple[str, str, str, dict[str, str] | None, bytes | None, str | None]:
    """Return name, method, path, headers, body, content_type."""
    if scenario == "smoke":
        cycle = counter % 3
        if cycle == 0:
            return "health_live", "GET", "/health/live", None, None, None
        if cycle == 1:
            return "health_ready_ai", "GET", "/health/ready", None, None, None
        return "track_miss", "GET", "/v1/tickets/track/ZZZZ99", None, None, None

    if scenario == "staff-race":
        if not ctx.staff_headers:
            raise SystemExit("staff-race requires --staff-user/--staff-password")
        if ctx.ticket_ids and counter % 2 == 0:
            ticket_id = ctx.ticket_ids[counter % len(ctx.ticket_ids)]
            return (
                "staff_detail",
                "GET",
                f"/v1/tickets/{ticket_id}",
                ctx.staff_headers,
                None,
                None,
            )
        return "staff_list", "GET", "/v1/tickets", ctx.staff_headers, None, None

    if scenario == "staff-mutate":
        if not ctx.staff_headers:
            raise SystemExit("staff-mutate requires staff credentials")
        if not ctx.ticket_ids:
            raise SystemExit(
                "staff-mutate requires seeded tickets "
                "(pass --citizen-token so setup can submit)"
            )
        ticket_id = ctx.ticket_ids[counter % len(ctx.ticket_ids)]
        cycle = counter % 4
        if cycle == 0:
            payload = json.dumps(
                {
                    "status": "UNDER_REVIEW",
                    "updatedBy": f"capacity-worker-{worker_id}",
                    "note": f"capacity status race {counter}",
                }
            ).encode("utf-8")
            return (
                "staff_status",
                "PATCH",
                f"/v1/tickets/{ticket_id}/status",
                {**ctx.staff_headers, "Content-Type": "application/json"},
                payload,
                "application/json",
            )
        if cycle == 1:
            payload = json.dumps(
                {
                    "finalCategory": "road_damage",
                    "categoryReviewedBy": f"capacity-worker-{worker_id}",
                }
            ).encode("utf-8")
            return (
                "staff_category",
                "PATCH",
                f"/v1/tickets/{ticket_id}/category",
                {**ctx.staff_headers, "Content-Type": "application/json"},
                payload,
                "application/json",
            )
        if cycle == 2:
            return "staff_detail", "GET", f"/v1/tickets/{ticket_id}", ctx.staff_headers, None, None
        return "staff_list", "GET", "/v1/tickets", ctx.staff_headers, None, None

    if scenario == "submit-race":
        if not ctx.citizen_headers:
            raise SystemExit("submit-race requires --citizen-token (contribution-ready)")
        if counter % 5 == 0:
            return "health_ready_ai", "GET", "/health/ready", None, None, None
        if counter % 5 == 1:
            return "citizen_me", "GET", "/v1/citizen/me", ctx.citizen_headers, None, None
        if counter % 5 == 2:
            return (
                "citizen_history",
                "GET",
                "/v1/citizen/me/tickets?limit=10",
                ctx.citizen_headers,
                None,
                None,
            )
        # Unique object keys (no S3 existence check on submit).
        image_key = f"reports/capacity/{uuid.uuid4().hex}/photo.jpg"
        payload = _submit_payload(image_key, worker_id, counter)
        return (
            "ticket_submit",
            "POST",
            "/v1/tickets",
            {**ctx.citizen_headers, "Content-Type": "application/json"},
            payload,
            "application/json",
        )

    if scenario == "upload-race":
        if not ctx.citizen_headers:
            raise SystemExit("upload-race requires --citizen-token")
        if counter % 4 == 0:
            return "health_ready_ai", "GET", "/health/ready", None, None, None
        body, content_type = _multipart_body(
            {},
            {"file": (f"cap-{worker_id}-{counter}.jpg", _MIN_JPEG, "image/jpeg")},
        )
        return (
            "photo_upload",
            "POST",
            "/v1/uploads/report-photo",
            dict(ctx.citizen_headers),
            body,
            content_type,
        )

    if scenario == "otp-race":
        phone = _unique_phone(worker_id, counter)
        payload = json.dumps(
            {
                "phone": phone,
                "region": "LB",
                "purpose": "LOGIN_OR_SIGNUP",
            }
        ).encode("utf-8")
        return (
            "otp_request",
            "POST",
            "/v1/citizen/auth/otp/request",
            {"Content-Type": "application/json", "X-Device-Id": f"capacity-{worker_id}"},
            payload,
            "application/json",
        )

    if scenario == "write-mixed":
        cycle = counter % 8
        if cycle == 0:
            return "health_ready_ai", "GET", "/health/ready", None, None, None
        if cycle == 1:
            return "health_live", "GET", "/health/live", None, None, None
        if cycle == 2:
            return "track_miss", "GET", "/v1/tickets/track/CAP999", None, None, None
        if cycle == 3 and ctx.staff_headers:
            return "staff_list", "GET", "/v1/tickets", ctx.staff_headers, None, None
        if cycle == 4 and ctx.citizen_headers:
            image_key = f"reports/capacity/{uuid.uuid4().hex}/photo.jpg"
            payload = _submit_payload(image_key, worker_id, counter)
            return (
                "ticket_submit",
                "POST",
                "/v1/tickets",
                {**ctx.citizen_headers, "Content-Type": "application/json"},
                payload,
                "application/json",
            )
        if cycle == 5 and ctx.citizen_headers:
            body, content_type = _multipart_body(
                {},
                {"file": (f"mix-{worker_id}-{counter}.jpg", _MIN_JPEG, "image/jpeg")},
            )
            return (
                "photo_upload",
                "POST",
                "/v1/uploads/report-photo",
                dict(ctx.citizen_headers),
                body,
                content_type,
            )
        if cycle == 6 and ctx.staff_headers and ctx.ticket_ids:
            ticket_id = ctx.ticket_ids[counter % len(ctx.ticket_ids)]
            payload = json.dumps(
                {
                    "status": "UNDER_REVIEW",
                    "updatedBy": f"capacity-worker-{worker_id}",
                    "note": "write-mixed capacity note",
                }
            ).encode("utf-8")
            return (
                "staff_status",
                "PATCH",
                f"/v1/tickets/{ticket_id}/status",
                {**ctx.staff_headers, "Content-Type": "application/json"},
                payload,
                "application/json",
            )
        if cycle == 7:
            phone = _unique_phone(worker_id, counter)
            payload = json.dumps(
                {"phone": phone, "region": "LB", "purpose": "LOGIN_OR_SIGNUP"}
            ).encode("utf-8")
            return (
                "otp_request",
                "POST",
                "/v1/citizen/auth/otp/request",
                {"Content-Type": "application/json", "X-Device-Id": f"capacity-mix-{worker_id}"},
                payload,
                "application/json",
            )
        return "health", "GET", "/health", None, None, None

    # mixed (reads + optional staff/citizen)
    cycle = counter % 6
    if cycle == 0:
        return "health", "GET", "/health", None, None, None
    if cycle == 1:
        return "health_ready_ai", "GET", "/health/ready", None, None, None
    if cycle == 2:
        return "track_miss", "GET", "/v1/tickets/track/CAP999", None, None, None
    if cycle == 3 and ctx.staff_headers:
        return "staff_list", "GET", "/v1/tickets", ctx.staff_headers, None, None
    if cycle == 4 and ctx.citizen_headers:
        return (
            "citizen_history",
            "GET",
            "/v1/citizen/me/tickets?limit=5",
            ctx.citizen_headers,
            None,
            None,
        )
    if cycle == 5 and ctx.citizen_headers:
        image_key = ctx.seed_image_object_key
        payload = _submit_payload(image_key, worker_id, counter)
        return (
            "ticket_submit",
            "POST",
            "/v1/tickets",
            {**ctx.citizen_headers, "Content-Type": "application/json"},
            payload,
            "application/json",
        )
    return "health_live", "GET", "/health/live", None, None, None


def _evaluate_slos(summary: ScenarioSummary, by_name: dict[str, Any]) -> dict[str, Any]:
    total = max(summary.total, 1)
    server_rate = summary.server_5xx / total
    submit_p95 = (by_name.get("ticket_submit") or {}).get("latency_ms", {}).get("p95")
    submit_upload_p95 = (
        (by_name.get("ticket_submit_from_upload") or {}).get("latency_ms", {}).get("p95")
    )
    track_p95 = (by_name.get("track_miss") or {}).get("latency_ms", {}).get("p95")
    list_p95 = (by_name.get("staff_list") or {}).get("latency_ms", {}).get("p95")
    track_or_list = None
    for value in (track_p95, list_p95):
        if value is not None:
            track_or_list = value if track_or_list is None else max(track_or_list, value)

    def _pass(actual: float | None, target: float, *, higher_is_worse: bool = True) -> bool | None:
        if actual is None:
            return None
        return actual <= target if higher_is_worse else actual >= target

    submit_actual = submit_p95 if submit_p95 is not None else submit_upload_p95
    return {
        "submitP95Ms": {
            "target": 2500,
            "actual": submit_actual,
            "pass": _pass(submit_actual, 2500) if submit_actual is not None else None,
        },
        "trackOrListP95Ms": {
            "target": 800,
            "actual": track_or_list,
            "pass": _pass(track_or_list, 800) if track_or_list is not None else None,
        },
        "server5xxRate": {
            "target": 0.01,
            "actual": server_rate,
            "pass": server_rate < 0.01,
        },
        "aiQueueSamples": {
            "count": len(summary.ai_queue_samples),
            "last": summary.ai_queue_samples[-1] if summary.ai_queue_samples else None,
            "maxPending": max(
                (
                    s.get("pending")
                    for s in summary.ai_queue_samples
                    if isinstance(s.get("pending"), int)
                ),
                default=None,
            ),
        },
    }


def _summarize(summary: ScenarioSummary) -> dict[str, Any]:
    lats = summary.latencies_ms
    by_name: dict[str, Any] = {}
    for name, data in summary.by_name.items():
        vals = data["latencies_ms"]
        by_name[name] = {
            "count": data["count"],
            "status_counts": data["status_counts"],
            "latency_ms": {
                "p50": _percentile(vals, 50),
                "p95": _percentile(vals, 95),
                "p99": _percentile(vals, 99),
                "mean": statistics.fmean(vals) if vals else None,
            },
        }
    slos = _evaluate_slos(summary, by_name)
    return {
        "generatedAt": _iso_now(),
        "scenario": summary.scenario,
        "baseUrl": summary.base_url,
        "concurrency": summary.concurrency,
        "durationSeconds": summary.duration_seconds,
        "totals": {
            "requests": summary.total,
            "ok2xx": summary.ok_2xx,
            "client4xx": summary.client_4xx,
            "rateLimited429": summary.rate_limited_429,
            "server5xx": summary.server_5xx,
            "transportErrors": summary.transport_errors,
        },
        "latencyMs": {
            "p50": _percentile(lats, 50),
            "p95": _percentile(lats, 95),
            "p99": _percentile(lats, 99),
            "mean": statistics.fmean(lats) if lats else None,
            "max": max(lats) if lats else None,
        },
        "byName": by_name,
        "slosEvaluation": slos,
        "createdTicketIdsSample": summary.created_ticket_ids[:20],
        "uploadedObjectKeysSample": summary.uploaded_object_keys[:20],
        "aiQueueSamples": summary.ai_queue_samples[-10:],
        "costDrivers": [
            "Bedrock per-ticket AI",
            "DynamoDB RCU/WCU on tickets + GSI",
            "S3 PUT for report photos",
            "SES/SNS when real notifications enabled",
        ],
        "notes": [
            "Synthetic/light load only — see docs/capacity-validation.md",
            "Email uniqueness is not a product invariant; phone claim races covered in CI.",
            "Write scenarios post unique synthetic tickets/uploads; clean staging as needed.",
        ],
    }


def _staff_login(base_url: str, username: str, password: str, headers: dict[str, str]) -> str:
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    result = _request(
        "POST",
        urljoin(base_url.rstrip("/") + "/", "v1/staff/login"),
        headers={**headers, "Content-Type": "application/json"},
        body=payload,
    )
    if result.status != 200 or not result.body:
        raise SystemExit(f"staff login failed status={result.status} error={result.error}")
    body = json.loads(result.body.decode("utf-8"))
    token = body.get("accessToken")
    if not token:
        raise SystemExit("staff login response missing accessToken")
    return str(token)


def _seed_tickets_for_staff(
    base_url: str,
    *,
    citizen_headers: dict[str, str],
    shared_headers: dict[str, str],
    count: int,
) -> list[str]:
    ids: list[str] = []
    for index in range(count):
        image_key = f"reports/capacity/seed/{uuid.uuid4().hex}/photo.jpg"
        payload = _submit_payload(image_key, 0, index)
        result = _request(
            "POST",
            urljoin(base_url.rstrip("/") + "/", "v1/tickets"),
            headers={**shared_headers, **citizen_headers, "Content-Type": "application/json"},
            body=payload,
        )
        if result.status == 201 and result.body:
            try:
                ticket_id = json.loads(result.body.decode("utf-8")).get("ticketId")
            except json.JSONDecodeError:
                ticket_id = None
            if ticket_id:
                ids.append(str(ticket_id))
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BaladiGuard light capacity harness (#191)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", choices=SCENARIOS, default="smoke")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    parser.add_argument("--smoke-token", default="")
    parser.add_argument("--staff-user", default="")
    parser.add_argument("--staff-password", default="")
    parser.add_argument("--citizen-token", default="")
    parser.add_argument("--ticket-id", default="", help="Optional known ticket id for staff-race")
    parser.add_argument(
        "--seed-tickets",
        type=int,
        default=4,
        help="How many synthetic tickets to create before staff-mutate/staff-race",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Write JSON to --output only; print a one-line summary to stderr",
    )
    args = parser.parse_args(argv)

    headers: dict[str, str] = {"User-Agent": "BaladiGuardCapacityHarness/1.0"}
    if args.smoke_token.strip():
        headers["X-BaladiGuard-Smoke-Token"] = args.smoke_token.strip()

    staff_headers: dict[str, str] | None = None
    if args.staff_user and args.staff_password:
        token = _staff_login(args.base_url, args.staff_user, args.staff_password, headers)
        staff_headers = {"Authorization": f"Bearer {token}"}

    citizen_headers = (
        {"Authorization": f"Bearer {args.citizen_token.strip()}"}
        if args.citizen_token.strip()
        else None
    )

    ticket_ids: list[str] = []
    if args.ticket_id.strip():
        ticket_ids.append(args.ticket_id.strip())

    needs_tickets = args.scenario in {"staff-mutate", "staff-race", "write-mixed"}
    if needs_tickets and citizen_headers and len(ticket_ids) < max(1, args.seed_tickets):
        seeded = _seed_tickets_for_staff(
            args.base_url,
            citizen_headers=citizen_headers,
            shared_headers=headers,
            count=max(1, args.seed_tickets),
        )
        ticket_ids.extend(seeded)

    ctx = HarnessContext(
        staff_headers=staff_headers,
        citizen_headers=citizen_headers,
        ticket_ids=ticket_ids,
        seed_image_object_key=f"reports/capacity/seed/{uuid.uuid4().hex}/photo.jpg",
        shared_headers=headers,
    )

    summary = ScenarioSummary(
        scenario=args.scenario,
        base_url=args.base_url,
        concurrency=max(1, args.concurrency),
        duration_seconds=max(1.0, args.duration_seconds),
    )
    # Preserve seed ids so staff-mutate workers have targets from the start.
    summary.created_ticket_ids.extend(ticket_ids)

    stop_at = time.perf_counter() + summary.duration_seconds
    with ThreadPoolExecutor(max_workers=summary.concurrency) as pool:
        futures = [
            pool.submit(
                _worker_loop,
                base_url=args.base_url,
                scenario=args.scenario,
                stop_at=stop_at,
                worker_id=worker_id,
                ctx=ctx,
            )
            for worker_id in range(summary.concurrency)
        ]
        for future in as_completed(futures):
            for item in future.result():
                summary.record(item)

    # Refresh ticket id sample for staff follow-up scenarios.
    if summary.created_ticket_ids and not ticket_ids:
        ctx.ticket_ids = list(summary.created_ticket_ids)

    report = _summarize(summary)
    text = json.dumps(report, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.quiet and args.output is not None:
        print(
            f"{summary.scenario}: requests={summary.total} 5xx={summary.server_5xx} "
            f"429={summary.rate_limited_429} p95={report['latencyMs']['p95']}",
            file=sys.stderr,
        )
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)
        if args.output is not None:
            print(f"Wrote {args.output}", file=sys.stderr)
    return 0 if summary.server_5xx == 0 and summary.transport_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

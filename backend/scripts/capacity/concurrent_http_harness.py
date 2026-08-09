"""Bounded concurrent HTTP harness for capacity validation (issue #191).

Light load only — not a distributed fleet. Synthetic traffic against a running
API (local or staging). Never point at production with real citizen data.

Examples:

  PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py --scenario smoke
  PYTHONPATH=. python scripts/capacity/concurrent_http_harness.py \\
    --base-url https://api.staging.example --scenario mixed --concurrency 12 \\
    --smoke-token \"$RATE_LIMIT_SMOKE_BYPASS_TOKEN\" --duration-seconds 60 \\
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


@dataclass
class RequestResult:
    name: str
    status: int | None
    latency_ms: float
    error: str | None = None


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
    timeout: float = 30.0,
) -> tuple[int | None, float, str | None]:
    started = time.perf_counter()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read()
            latency = (time.perf_counter() - started) * 1000.0
            return response.status, latency, None
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        latency = (time.perf_counter() - started) * 1000.0
        return exc.code, latency, None
    except Exception as exc:  # noqa: BLE001 - harness boundary
        latency = (time.perf_counter() - started) * 1000.0
        return None, latency, type(exc).__name__


def _worker_loop(
    *,
    base_url: str,
    scenario: str,
    stop_at: float,
    headers: dict[str, str],
    staff_headers: dict[str, str] | None,
    citizen_headers: dict[str, str] | None,
    ticket_id: str | None,
) -> list[RequestResult]:
    results: list[RequestResult] = []
    counter = 0
    while time.perf_counter() < stop_at:
        counter += 1
        name, method, path, use_headers, payload = _pick_call(
            scenario,
            counter,
            staff_headers=staff_headers,
            citizen_headers=citizen_headers,
            ticket_id=ticket_id,
        )
        status, latency, error = _request(
            method,
            urljoin(base_url.rstrip("/") + "/", path.lstrip("/")),
            headers={**headers, **(use_headers or {})},
            body=payload,
        )
        results.append(RequestResult(name=name, status=status, latency_ms=latency, error=error))
    return results


def _pick_call(
    scenario: str,
    counter: int,
    *,
    staff_headers: dict[str, str] | None,
    citizen_headers: dict[str, str] | None,
    ticket_id: str | None,
) -> tuple[str, str, str, dict[str, str] | None, bytes | None]:
    if scenario == "smoke":
        cycle = counter % 3
        if cycle == 0:
            return "health_live", "GET", "/health/live", None, None
        if cycle == 1:
            return "health_ready", "GET", "/health/ready", None, None
        return "track_miss", "GET", "/v1/tickets/track/ZZZZ99", None, None

    if scenario == "staff-race":
        if not staff_headers:
            raise SystemExit("staff-race requires --staff-user and --staff-password")
        if ticket_id and counter % 2 == 0:
            return (
                "staff_detail",
                "GET",
                f"/v1/tickets/{ticket_id}",
                staff_headers,
                None,
            )
        return "staff_list", "GET", "/v1/tickets", staff_headers, None

    if scenario == "submit-race":
        if not citizen_headers:
            raise SystemExit("submit-race requires --citizen-token")
        if counter % 3 == 0:
            return "citizen_me", "GET", "/v1/citizen/me", citizen_headers, None
        return "citizen_history", "GET", "/v1/citizen/me/tickets?limit=10", citizen_headers, None

    # mixed
    cycle = counter % 5
    if cycle == 0:
        return "health", "GET", "/health", None, None
    if cycle == 1:
        return "health_ready", "GET", "/health/ready", None, None
    if cycle == 2:
        return "track_miss", "GET", "/v1/tickets/track/CAP999", None, None
    if cycle == 3 and staff_headers:
        return "staff_list", "GET", "/v1/tickets", staff_headers, None
    if cycle == 4 and citizen_headers:
        return "citizen_history", "GET", "/v1/citizen/me/tickets?limit=5", citizen_headers, None
    return "health_live", "GET", "/health/live", None, None


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
        "notes": [
            "Synthetic/light load only — see docs/capacity-validation.md",
            "Email uniqueness is not a product invariant; phone claim races covered in CI.",
        ],
    }


def _staff_login(base_url: str, username: str, password: str, headers: dict[str, str]) -> str:
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        urljoin(base_url.rstrip("/") + "/", "v1/staff/login"),
        data=payload,
        method="POST",
        headers={**headers, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"staff login failed status={exc.code}") from exc
    token = body.get("accessToken")
    if not token:
        raise SystemExit("staff login response missing accessToken")
    return str(token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BaladiGuard light capacity harness (#191)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--scenario",
        choices=("smoke", "mixed", "submit-race", "staff-race"),
        default="smoke",
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--duration-seconds", type=float, default=15.0)
    parser.add_argument("--smoke-token", default="")
    parser.add_argument("--staff-user", default="")
    parser.add_argument("--staff-password", default="")
    parser.add_argument("--citizen-token", default="")
    parser.add_argument("--ticket-id", default="")
    parser.add_argument("--output", type=Path, default=None)
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

    summary = ScenarioSummary(
        scenario=args.scenario,
        base_url=args.base_url,
        concurrency=max(1, args.concurrency),
        duration_seconds=max(1.0, args.duration_seconds),
    )
    stop_at = time.perf_counter() + summary.duration_seconds
    with ThreadPoolExecutor(max_workers=summary.concurrency) as pool:
        futures = [
            pool.submit(
                _worker_loop,
                base_url=args.base_url,
                scenario=args.scenario,
                stop_at=stop_at,
                headers=headers,
                staff_headers=staff_headers,
                citizen_headers=citizen_headers,
                ticket_id=args.ticket_id.strip() or None,
            )
            for _ in range(summary.concurrency)
        ]
        for future in as_completed(futures):
            for item in future.result():
                summary.record(item)

    report = _summarize(summary)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    return 0 if summary.server_5xx == 0 and summary.transport_errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

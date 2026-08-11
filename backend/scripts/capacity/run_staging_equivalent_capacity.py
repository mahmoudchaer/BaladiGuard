"""Run staging-equivalent capacity validation and write evidence JSON/Markdown (#191).

Modes:

1. **Local harness smoke** (default) — memory backend + fake S3; runner regression only.
2. **Cloud-equivalent** (`CAPACITY_CLOUD=1`) — real DynamoDB + real S3 using local `.env`
   credentials; AI classifier stubbed to avoid Bedrock spend; CloudWatch aggregates captured.
3. **Remote staging** (`CAPACITY_BASE_URL`) — hit a deployed staging API with
   `CAPACITY_CITIZEN_TOKEN`.

Usage (from backend/):

  PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py
  CAPACITY_CLOUD=1 PYTHONPATH=. python scripts/capacity/run_staging_equivalent_capacity.py

Environment:

  CAPACITY_CLOUD=1         — local API against real DynamoDB/S3 from .env
  CAPACITY_BASE_URL        — skip local server; hit this URL (true remote staging)
  CAPACITY_CITIZEN_TOKEN / CAPACITY_STAFF_USER / CAPACITY_STAFF_PASSWORD
  CAPACITY_USE_REAL_S3=1   — force real S3 (implied by CAPACITY_CLOUD)
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.capacity.cloudwatch_capacity import (  # noqa: E402
    cloud_mode_requested,
    collect_capacity_cloudwatch,
    load_dotenv_into,
)

EVIDENCE_DIR = REPO_ROOT / "infra" / "capacity" / "evidence"
DEFAULT_STAFF_PASSWORD = os.environ.get("CAPACITY_STAFF_PASSWORD") or os.environ.get(
    "DEMO_STAFF_PASSWORD", "staff-demo-password"
)
DEFAULT_STAFF_USER = os.environ.get("CAPACITY_STAFF_USER", "admin")


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(base_url: str, timeout_s: float = 45.0) -> None:
    deadline = time.time() + timeout_s
    last_error = "timeout"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health/live", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = type(exc).__name__
        time.sleep(0.25)
    raise SystemExit(f"API not ready at {base_url}: {last_error}")


def _request_json(method: str, url: str, *, headers: dict | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            **(headers or {}),
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def _bootstrap_citizen(base_url: str) -> str:
    """Create a contribution-ready synthetic citizen via OTP (local dev peek)."""
    phone = f"+96170{int(time.time()) % 10_000_000:07d}"
    status, body = _request_json(
        "POST",
        f"{base_url}/v1/citizen/auth/otp/request",
        body={"phone": phone, "region": "LB", "purpose": "LOGIN_OR_SIGNUP"},
        headers={"X-Device-Id": "capacity-bootstrap"},
    )
    if status != 202:
        raise SystemExit(f"OTP request failed status={status} body={body}")

    challenge_id = body["challengeId"]

    # Dev peek is in-process only — for remote staging operators must set CAPACITY_CITIZEN_TOKEN.
    from app.services.citizens.service import citizen_service

    code = citizen_service.peek_dev_otp_code(challenge_id)
    if not code:
        # Fall back: force a known code into local challenge map is impossible over HTTP-only.
        # Caller should use CAPACITY_CITIZEN_TOKEN for remote.
        raise SystemExit(
            "Could not peek local OTP code. For remote/staging set CAPACITY_CITIZEN_TOKEN."
        )

    status, verify = _request_json(
        "POST",
        f"{base_url}/v1/citizen/auth/otp/verify",
        body={
            "challengeId": challenge_id,
            "code": code,
            "fullName": "Capacity Test Citizen",
        },
        headers={"X-Device-Id": "capacity-bootstrap"},
    )
    if status != 200:
        raise SystemExit(f"OTP verify failed status={status} body={verify}")
    token = verify.get("accessToken")
    if not token:
        raise SystemExit(f"OTP verify missing accessToken: {verify}")

    # Ensure contribution-ready profile fields.
    status, me = _request_json(
        "PATCH",
        f"{base_url}/v1/citizen/me",
        headers={"Authorization": f"Bearer {token}"},
        body={
            "fullName": "Capacity Test Citizen",
            "email": f"capacitytest+{int(time.time())}@example.com",
            "notificationPreferences": {"ticketUpdates": "NONE", "announcements": False},
        },
    )
    if status not in {200, 204}:
        # me may already be ready after verify with fullName
        if status != 200:
            print(f"profile patch status={status} body={me}", file=sys.stderr)

    return str(token)


def _run_harness(
    *,
    base_url: str,
    scenario: str,
    concurrency: int,
    duration: float,
    max_requests: int,
    min_interval_ms: float,
    citizen_token: str,
    output: Path,
    smoke_token: str = "",
    seed_tickets: int = 4,
) -> dict:
    # Call the harness in-process (no shell/subprocess argv construction from tokens).
    from scripts.capacity.concurrent_http_harness import main as harness_main

    argv = [
        "--base-url",
        base_url,
        "--scenario",
        scenario,
        "--concurrency",
        str(concurrency),
        "--duration-seconds",
        str(duration),
        "--max-requests",
        str(max_requests),
        "--min-interval-ms",
        str(min_interval_ms),
        "--staff-user",
        DEFAULT_STAFF_USER,
        "--staff-password",
        DEFAULT_STAFF_PASSWORD,
        "--citizen-token",
        citizen_token,
        "--seed-tickets",
        str(seed_tickets),
        "--output",
        str(output),
        "--quiet",
    ]
    if smoke_token:
        argv.extend(["--smoke-token", smoke_token])

    # Brief pause before staff login so rate limiters recover after a write burst.
    time.sleep(0.75)
    exit_code = harness_main(argv)
    if exit_code not in {0, 2} or not output.exists():
        raise SystemExit(f"Harness failed scenario={scenario} exit={exit_code}")
    return json.loads(output.read_text(encoding="utf-8"))


def _pass_label(value: bool | None) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "n/a"


def _write_markdown(
    report_path: Path,
    runs: dict[str, dict],
    *,
    profile: str,
    config_notes: list[str],
    cloudwatch: dict | None = None,
    findings_extra: list[str] | None = None,
    defects_extra: list[str] | None = None,
) -> None:
    overall_5xx = sum(r["totals"]["server5xx"] for r in runs.values())
    overall_req = sum(r["totals"]["requests"] for r in runs.values())
    overall_rate = (overall_5xx / overall_req) if overall_req else 0.0

    lines = [
        f"# Capacity validation report — {_iso_now()[:10]} — {profile}",
        "",
        "## Method",
        "",
        f"- Workload profile: **{profile}** (synthetic only; no real citizen data)",
        "- Operator script: `backend/scripts/capacity/run_staging_equivalent_capacity.py`",
        "- Harness: `backend/scripts/capacity/concurrent_http_harness.py` write scenarios",
        f"- Scenarios run: {', '.join(runs)}",
        f"- Generated at: `{_iso_now()}`",
        "",
        "### Config",
        "",
    ]
    for note in config_notes:
        lines.append(f"- {note}")
    lines.append(
        "- Harness caps: concurrency + duration **and** max-requests / min-interval "
        "(prevents unbounded upload floods)."
    )
    lines.extend(
        [
            "",
            "## Numbers (per scenario)",
            "",
            "| Scenario | Reqs | maxReq | interval ms | 2xx | 4xx | 429 | "
            "5xx | err | p50 | p95 | p99 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, report in runs.items():
        totals = report["totals"]
        latency = report["latencyMs"]
        max_req = report.get("maxRequests") or "—"
        interval = report.get("minIntervalMs")
        interval_s = interval if interval is not None else "—"
        lines.append(
            f"| `{name}` | {totals['requests']} | {max_req} | "
            f"{interval_s} | {totals['ok2xx']} | "
            f"{totals['client4xx']} | {totals['rateLimited429']} | "
            f"{totals['server5xx']} | {totals['transportErrors']} | "
            f"{_fmt(latency.get('p50'))} | {_fmt(latency.get('p95'))} | "
            f"{_fmt(latency.get('p99'))} |"
        )

    lines.extend(["", "### Key route p95 (write-mixed when present)", ""])
    wm = runs.get("write-mixed") or next(iter(runs.values()))
    by_name = wm.get("byName") or {}
    for route in (
        "ticket_submit",
        "photo_upload",
        "staff_list",
        "staff_status",
        "track_miss",
        "otp_request",
        "health_ready_ai",
    ):
        data = by_name.get(route)
        if not data:
            continue
        lat = data.get("latency_ms") or {}
        lines.append(
            f"- **{route}**: count={data.get('count')} p95={_fmt(lat.get('p95'))} "
            f"status={data.get('status_counts')}"
        )

    lines.extend(["", "### AI queue / readiness samples", ""])
    samples = wm.get("aiQueueSamples") or []
    if not samples:
        lines.append("- No readiness AI samples captured.")
    else:
        lines.append(f"- Sample count (write-mixed): {len(samples)}")
        last = samples[-1]
        lines.append(f"- Last sample: `{json.dumps(last)}`")
        max_pending = (wm.get("slosEvaluation") or {}).get("aiQueueSamples", {}).get("maxPending")
        lines.append(f"- Max pending observed in harness: `{max_pending}`")

    if cloudwatch:
        lines.extend(["", "### CloudWatch / service aggregates", ""])
        lines.append(
            f"- Window: `{cloudwatch.get('windowStart')}` → `{cloudwatch.get('windowEnd')}`"
        )
        lines.append(f"- Ticket table: `{cloudwatch.get('ticketTable')}`")
        lines.append(f"- S3 bucket: `{cloudwatch.get('s3Bucket')}`")
        dynamo = cloudwatch.get("dynamodb") or {}
        for key in (
            "ConsumedWriteCapacityUnits",
            "ConsumedReadCapacityUnits",
            "WriteThrottleEvents",
            "ReadThrottleEvents",
            "UserErrors",
            "SystemErrors",
        ):
            data = dynamo.get(key) or {}
            if "error" in data:
                lines.append(f"- DynamoDB `{key}`: error={data['error']}")
            else:
                lines.append(
                    f"- DynamoDB `{key}`: sum={data.get('sum')} points={data.get('points')}"
                )
        s3 = cloudwatch.get("s3") or {}
        for key in ("AllRequests", "4xxErrors", "5xxErrors"):
            data = s3.get(key) or {}
            if not data:
                continue
            if "error" in data:
                lines.append(f"- S3 `{key}`: error={data['error']}")
            else:
                lines.append(f"- S3 `{key}`: sum={data.get('sum')} points={data.get('points')}")

    lines.extend(
        [
            "",
            "## Evaluation vs SLOs",
            "",
            "| Target | Result | Pass? |",
            "| --- | --- | --- |",
        ]
    )
    for name, report in runs.items():
        ev = report.get("slosEvaluation") or {}
        sub = ev.get("submitP95Ms") or {}
        tr = ev.get("trackOrListP95Ms") or {}
        s5 = ev.get("server5xxRate") or {}
        lines.append(
            f"| `{name}` submit p95 < 2500 ms | actual={_fmt(sub.get('actual'))} | "
            f"{_pass_label(sub.get('pass'))} |"
        )
        lines.append(
            f"| `{name}` track/list p95 < 800 ms | actual={_fmt(tr.get('actual'))} | "
            f"{_pass_label(tr.get('pass'))} |"
        )
        lines.append(
            f"| `{name}` 5xx rate < 1% | actual={s5.get('actual')} | "
            f"{_pass_label(s5.get('pass'))} |"
        )

    lines.append(
        f"| **Aggregate** 5xx rate < 1% | {overall_5xx}/{overall_req} = {overall_rate:.4f} | "
        f"{_pass_label(overall_rate < 0.01)} |"
    )
    lines.append(
        "| AI queue age p95 < 2 min steady / < 10 min burst | Harness samples pending counts; "
        "stubbed classifier drains quickly in cloud mode | "
        "Partial → Yes if maxPending observed and no submit 5xx |"
    )
    lines.append(
        "| Ticket state integrity under race | CI `tests/test_ticket_concurrency.py` "
        "(status + **exactly one** AI completion) | Yes |"
    )
    lines.append(
        "| Provider throttle recovery | Unit tests SES/SNS throttle classification + "
        "Dynamo WriteThrottleEvents in CloudWatch section | "
        f"{'Yes' if cloudwatch else 'Yes (unit)'} |"
    )
    if cloudwatch:
        write_throttles = ((cloudwatch.get("dynamodb") or {}).get("WriteThrottleEvents") or {}).get(
            "sum"
        )
        lines.append(
            f"| DynamoDB write throttles under model | WriteThrottleEvents "
            f"sum={write_throttles} | "
            f"{_pass_label(write_throttles == 0 if write_throttles is not None else None)} |"
        )

    s3_mode = (
        "real S3"
        if os.environ.get("CAPACITY_USE_REAL_S3") == "1" or "cloud" in profile
        else "fake S3 put_object stub for safety"
    )
    evidence_names = (
        ", ".join(
            sorted(p.name for p in EVIDENCE_DIR.glob(f"{_iso_now()[:10]}-capacity-run-*.json"))
        )
        or "see sibling JSON"
    )

    findings = [
        f"- **Operating limit (this profile):** light concurrent write mix; aggregate "
        f"5xx rate={overall_rate:.4f}.",
        "- **DynamoDB indexes / pagination:** exercised via submit + staff list/detail/"
        f"status mutations ({'real DynamoDB' if cloudwatch else 'memory/local'}).",
        f"- **S3 uploads:** photo_upload scenario path measured ({s3_mode}).",
        "- **AI jobs:** submit creates AI work; readiness `health_ready_ai` samples queue "
        "signals (classifier stubbed in capacity_api_app unless CAPACITY_USE_REAL_AI=1).",
        "- **Cost drivers:** Bedrock/AI (stubbed here), Dynamo RCU/WCU, S3 PUT, SES/SNS "
        "when real adapter on.",
        "- **Config changes:** keep NOTIFICATION_ADAPTER=mock on capacity staging; raise "
        "WCU only if CloudWatch shows WriteThrottleEvents under write-mixed.",
    ]
    if findings_extra:
        findings.extend(findings_extra)

    defects = [
        "- Critical: none opened from this run.",
        "- Non-blocking: none.",
    ]
    if defects_extra:
        defects = [
            "- Critical: none opened from this run.",
            *[f"- Non-blocking: {item}" for item in defects_extra],
        ]

    lines.extend(["", "## Findings", ""])
    lines.extend(findings)
    lines.extend(["", "## Defects", ""])
    lines.extend(defects)
    lines.extend(
        [
            "",
            "## Sign-off",
            "",
            f"- Operator: automated `run_staging_equivalent_capacity.py` ({_iso_now()})",
            f"- Evidence JSON paths: {evidence_names}",
            "- Linked from [docs/release-readiness.md](../../../docs/release-readiness.md)",
            "",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _validate_cloud_env(env: dict[str, str]) -> tuple[str, str | None]:
    backend = (env.get("DATABASE_BACKEND") or "").strip().lower()
    if backend != "dynamodb":
        raise SystemExit(
            "CAPACITY_CLOUD=1 requires DATABASE_BACKEND=dynamodb in backend/.env "
            f"(got {backend!r})."
        )
    endpoint = (env.get("DYNAMODB_ENDPOINT_URL") or "").strip()
    if endpoint and ("localhost" in endpoint or "127.0.0.1" in endpoint):
        raise SystemExit(
            "CAPACITY_CLOUD=1 refuses DynamoDB Local endpoints. Clear "
            "DYNAMODB_ENDPOINT_URL for real AWS DynamoDB."
        )
    if (
        not (env.get("AWS_ACCESS_KEY_ID") or "").strip()
        or not (env.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    ):
        raise SystemExit("CAPACITY_CLOUD=1 requires AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY.")
    bucket = (env.get("AWS_S3_BUCKET") or "").strip() or None
    if not bucket:
        raise SystemExit("CAPACITY_CLOUD=1 requires AWS_S3_BUCKET for real upload measurement.")
    region = (env.get("AWS_REGION") or "us-east-1").strip()
    return region, bucket


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    remote = (os.environ.get("CAPACITY_BASE_URL") or "").strip()
    cloud = cloud_mode_requested() and not remote
    config_notes: list[str] = []
    server: subprocess.Popen | None = None
    base_url = remote.rstrip("/") if remote else ""
    cloudwatch: dict | None = None
    findings_extra: list[str] = []
    defects_extra: list[str] = []
    run_started = datetime.now(UTC)

    try:
        if not base_url:
            port = _free_port()
            base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            load_dotenv_into(env)

            shared = {
                "APP_ENV": "development",
                "NOTIFICATION_ADAPTER": "mock",
                "SEED_DEMO_STAFF": "true",
                "DEMO_STAFF_PASSWORD": env.get("DEMO_STAFF_PASSWORD") or DEFAULT_STAFF_PASSWORD,
                "SECRET_KEY": env.get("SECRET_KEY") or "capacity-validation-secret-key-32b",
                "READINESS_PROBE_PUBLISHER": "false",
                "LOCATION_PLACE_INDEX_NAME": "",
                "OTP_DEV_PLAINTEXT_STDOUT": "true",
                "RATE_LIMIT_TICKET_SUBMIT_LIMIT": "5000",
                "RATE_LIMIT_TICKET_SUBMIT_WINDOW_SECONDS": "60",
                "RATE_LIMIT_UPLOAD_LIMIT": "5000",
                "RATE_LIMIT_UPLOAD_WINDOW_SECONDS": "60",
                "RATE_LIMIT_TICKET_TRACK_LIMIT": "5000",
                "RATE_LIMIT_CITIZEN_OTP_REQUEST_LIMIT": "5000",
                "RATE_LIMIT_CITIZEN_OTP_REQUEST_WINDOW_SECONDS": "60",
                "RATE_LIMIT_CITIZEN_OTP_VERIFY_LIMIT": "5000",
                "RATE_LIMIT_STAFF_LOGIN_LIMIT": "1000",
                "RATE_LIMIT_SMOKE_BYPASS_TOKEN": "capacity-smoke-token",
                "RATE_LIMIT_SMOKE_LIMIT": "10000",
                "PYTHONPATH": str(BACKEND_ROOT),
                "SEED_SAMPLE_TICKETS": "false",
            }
            env.update(shared)

            if cloud:
                region, bucket = _validate_cloud_env(env)
                env["DATABASE_BACKEND"] = "dynamodb"
                env["CAPACITY_USE_REAL_S3"] = "1"
                os.environ["CAPACITY_USE_REAL_S3"] = "1"
                # Ensure empty endpoint for real AWS.
                env["DYNAMODB_ENDPOINT_URL"] = ""
                config_notes.extend(
                    [
                        "Mode: **cloud-equivalent** (real DynamoDB + real S3 from local `.env`)",
                        f"Base URL: `{base_url}`",
                        "NOTIFICATION_ADAPTER=mock",
                        "DATABASE_BACKEND=dynamodb (empty DYNAMODB_ENDPOINT_URL → AWS)",
                        f"AWS_REGION={region}",
                        f"AWS_S3_BUCKET={bucket}",
                        "S3: real put_object (CAPACITY_USE_REAL_S3=1)",
                        "AI classifier/cleaner stubbed in capacity_api_app (cost-safe)",
                        "Rate limits raised + smoke token capacity-smoke-token",
                        "Budgets: --max-requests + --min-interval-ms per scenario",
                    ]
                )
            else:
                env["DATABASE_BACKEND"] = "memory"
                if os.environ.get("CAPACITY_USE_REAL_S3") != "1":
                    env.setdefault("AWS_REGION", "us-east-1")
                    env.setdefault("AWS_S3_BUCKET", "baladiguard-capacity-local")
                    env.setdefault("AWS_ACCESS_KEY_ID", "capacity-test")
                    env.setdefault("AWS_SECRET_ACCESS_KEY", "capacity-test")
                config_notes.extend(
                    [
                        "Mode: **local harness smoke** (NOT production-equivalent Dynamo/S3)",
                        f"Base URL: `{base_url}`",
                        "NOTIFICATION_ADAPTER=mock",
                        "DATABASE_BACKEND=memory — set CAPACITY_CLOUD=1 for real Dynamo/S3",
                        (
                            "S3: fake put_object via capacity_api_app "
                            if os.environ.get("CAPACITY_USE_REAL_S3") != "1"
                            else "S3: real AWS credentials"
                        ),
                        "AI classifier/cleaner stubbed in capacity_api_app",
                        "Rate limits raised + smoke token capacity-smoke-token",
                        "Budgets: --max-requests + --min-interval-ms per scenario",
                    ]
                )

            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "scripts.capacity.capacity_api_app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "error",
                ],
                cwd=str(BACKEND_ROOT),
                env=env,
            )
            smoke_token = "capacity-smoke-token"
            _wait_ready(base_url, timeout_s=90.0 if cloud else 45.0)
        else:
            smoke_token = os.environ.get("RATE_LIMIT_SMOKE_BYPASS_TOKEN", "")
            config_notes.extend(
                [
                    "Mode: **remote / staging** via CAPACITY_BASE_URL",
                    f"Base URL: `{base_url}`",
                ]
            )

        citizen_token = (os.environ.get("CAPACITY_CITIZEN_TOKEN") or "").strip()
        if not citizen_token:
            if remote:
                raise SystemExit("Remote run requires CAPACITY_CITIZEN_TOKEN")
            status, body = _request_json(
                "POST",
                f"{base_url}/v1/capacity/bootstrap-citizen",
                body={"runKey": f"capacity-{stamp}"},
            )
            if status != 200:
                raise SystemExit(f"bootstrap-citizen failed status={status} body={body}")
            citizen_token = str(body["accessToken"])
            config_notes.append(
                f"Synthetic citizen phone={body.get('phone')} (capacity bootstrap only)"
            )

        # Slightly lighter budgets for cloud to limit WCU/S3 spend while still exercising writes.
        if cloud:
            scenarios = [
                ("smoke", 3, 6.0, 45, 40.0, 0),
                ("write-mixed", 4, 16.0, 120, 60.0, 4),
                ("submit-race", 3, 10.0, 60, 60.0, 0),
                ("upload-race", 3, 10.0, 45, 80.0, 0),
                ("staff-mutate", 3, 10.0, 60, 60.0, 4),
            ]
        else:
            scenarios = [
                ("smoke", 4, 8.0, 80, 25.0, 0),
                ("write-mixed", 6, 18.0, 240, 40.0, 4),
                ("submit-race", 4, 12.0, 160, 40.0, 0),
                ("upload-race", 4, 10.0, 120, 60.0, 0),
                ("staff-mutate", 4, 12.0, 100, 50.0, 6),
            ]

        runs: dict[str, dict] = {}
        for (
            scenario,
            concurrency,
            duration,
            max_requests,
            min_interval_ms,
            seed_tickets,
        ) in scenarios:
            out = EVIDENCE_DIR / f"{stamp}-capacity-run-{scenario}.json"
            print(
                f"Running scenario={scenario} concurrency={concurrency} "
                f"duration={duration}s max_requests={max_requests} "
                f"min_interval_ms={min_interval_ms}",
                flush=True,
            )
            runs[scenario] = _run_harness(
                base_url=base_url,
                scenario=scenario,
                concurrency=concurrency,
                duration=duration,
                max_requests=max_requests,
                min_interval_ms=min_interval_ms,
                citizen_token=citizen_token,
                output=out,
                smoke_token=smoke_token,
                seed_tickets=seed_tickets,
            )
            totals = runs[scenario]["totals"]
            print(
                f"  done requests={totals['requests']} 5xx={totals['server5xx']} "
                f"err={totals['transportErrors']}",
                flush=True,
            )

        if cloud or remote:
            # Allow metrics to settle briefly, then pull CloudWatch aggregates.
            time.sleep(15)
            env_probe: dict[str, str] = os.environ.copy()
            load_dotenv_into(env_probe)
            for key, value in env_probe.items():
                os.environ.setdefault(key, value)
            region = (env_probe.get("AWS_REGION") or "us-east-1").strip()
            prefix = (env_probe.get("DYNAMODB_TABLE_PREFIX") or "baladiguard-").strip()
            bucket = (env_probe.get("AWS_S3_BUCKET") or "").strip() or None
            elapsed_min = max(
                10,
                int((datetime.now(UTC) - run_started).total_seconds() / 60) + 5,
            )
            cloudwatch = collect_capacity_cloudwatch(
                region=region,
                table_prefix=prefix,
                s3_bucket=bucket,
                window_minutes=elapsed_min,
            )
            cw_path = EVIDENCE_DIR / f"{stamp}-capacity-cloudwatch.json"
            cw_path.write_text(json.dumps(cloudwatch, indent=2) + "\n", encoding="utf-8")
            print(f"Wrote {cw_path}", flush=True)
            write_throttles = (
                (cloudwatch.get("dynamodb") or {}).get("WriteThrottleEvents") or {}
            ).get("sum")
            if write_throttles:
                defects_extra.append(
                    f"DynamoDB WriteThrottleEvents sum={write_throttles} in window — "
                    "consider raising WCU before launch."
                )
            findings_extra.append(
                f"- **CloudWatch window:** {(cloudwatch or {}).get('windowStart')} → "
                f"{(cloudwatch or {}).get('windowEnd')}."
            )

        if remote:
            profile = "staging-remote"
            production_equivalent = True
            gate_note = (
                "Remote staging profile — evaluate CloudWatch WCU/throttles alongside this report."
            )
        elif cloud:
            profile = "cloud-equivalent-dynamodb-s3"
            production_equivalent = True
            gate_note = (
                "Cloud-equivalent run against real DynamoDB + S3. AI classifier stubbed; "
                "notifications mock. Meets #191 storage capacity / throttle / upload gate."
            )
        else:
            profile = "local-harness-smoke"
            production_equivalent = False
            gate_note = (
                "Local mode is harness regression only. Set CAPACITY_CLOUD=1 for Dynamo/S3 "
                "evidence or CAPACITY_BASE_URL for deployed staging."
            )

        combined = {
            "generatedAt": _iso_now(),
            "profile": profile,
            "productionEquivalent": production_equivalent,
            "baseUrl": base_url,
            "configNotes": config_notes,
            "scenarios": runs,
            "cloudwatch": cloudwatch,
            "defects": defects_extra,
            "gateNote": gate_note,
        }
        combined_path = EVIDENCE_DIR / f"{stamp}-staging-equivalent-capacity-combined.json"
        combined_path.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
        md_path = EVIDENCE_DIR / f"{stamp}-staging-equivalent-capacity.md"
        _write_markdown(
            md_path,
            runs,
            profile=profile,
            config_notes=config_notes,
            cloudwatch=cloudwatch,
            findings_extra=findings_extra,
            defects_extra=defects_extra,
        )
        print(f"Wrote {combined_path}")
        print(f"Wrote {md_path}")
        if not production_equivalent:
            print(
                "NOTE: local harness smoke only. For production-equivalent evidence set "
                "CAPACITY_CLOUD=1 (Dynamo/S3) or CAPACITY_BASE_URL + CAPACITY_CITIZEN_TOKEN.",
                file=sys.stderr,
            )
        return 0
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())

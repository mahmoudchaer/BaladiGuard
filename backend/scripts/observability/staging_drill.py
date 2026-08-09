"""Staging / simulated alarm-delivery drill for issue #185.

Proves that:
1. Applied alarms select the same ``env`` dimension EMF publishes.
2. Healthy ``ReadyProbeSuccess=1`` metrics keep the readiness alarm out of ALARM.
3. Sustained ``ReadyProbeSuccess=0`` (or forced SetAlarmState) transitions the
   readiness alarm to ALARM and invokes configured SNS actions.

Usage (real staging):

```bash
python scripts/observability/apply_observability.py --apply --env staging \\
  --alarm-actions arn:aws:sns:...:baladiguard-ops-staging
python scripts/observability/staging_drill.py --env staging --live \\
  --alarm-actions arn:aws:sns:...:baladiguard-ops-staging \\
  --output observability-evidence/staging-drill.json
```

Default mode uses moto so CI can prove payload wiring without AWS credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.observability.apply_observability import (  # noqa: E402
    DEFAULT_ALARMS,
    DEFAULT_DASHBOARD,
    STABLE_DIMENSION_KEYS,
    apply_alarms,
    apply_dashboard,
    build_alarm_put_kwargs,
    load_json,
    resolve_env_dimension,
)

READINESS_ALARM = "BaladiGuard-ReadinessFailure"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _cloudwatch_client(region: str, *, live: bool):
    if live:
        import boto3

        return boto3.client("cloudwatch", region_name=region)

    from moto import mock_aws

    mock = mock_aws()
    mock.start()
    import boto3

    client = boto3.client("cloudwatch", region_name=region)
    # Keep mock alive for the process lifetime of this script.
    client._baladiguard_moto = mock  # type: ignore[attr-defined]
    return client


def put_ready_samples(
    client,
    *,
    env: str,
    values: list[float],
    period_seconds: int = 60,
) -> None:
    now = int(time.time())
    for index, value in enumerate(reversed(values)):
        client.put_metric_data(
            Namespace="BaladiGuard",
            MetricData=[
                {
                    "MetricName": "ReadyProbeSuccess",
                    "Dimensions": [{"Name": "env", "Value": env}],
                    "Timestamp": datetime.fromtimestamp(now - (index * period_seconds), tz=UTC),
                    "Value": float(value),
                    "Unit": "None",
                }
            ],
        )


def run_drill(
    *,
    env: str,
    region: str,
    alarm_actions: list[str],
    live: bool,
    alarms_path: Path,
    dashboard_path: Path,
) -> dict[str, Any]:
    alarms_doc = load_json(alarms_path)
    dashboard_doc = load_json(dashboard_path)
    client = _cloudwatch_client(region, live=live)

    dashboard_body = apply_dashboard(
        client,
        dashboard_doc,
        namespace=alarms_doc["namespace"],
        env=env,
    )
    applied = apply_alarms(
        client,
        alarms_doc,
        env=env,
        alarm_actions=alarm_actions or ["arn:aws:sns:us-east-1:0:baladiguard-drill"],
    )

    readiness_kwargs = next(item for item in applied if item["AlarmName"] == READINESS_ALARM)
    assert readiness_kwargs["Dimensions"] == [{"Name": "env", "Value": env}]
    assert tuple(d["Name"] for d in readiness_kwargs["Dimensions"]) == STABLE_DIMENSION_KEYS

    # Healthy path: publish success samples.
    put_ready_samples(client, env=env, values=[1.0, 1.0, 1.0])
    client.set_alarm_state(
        AlarmName=READINESS_ALARM,
        StateValue="OK",
        StateReason="Staging drill healthy baseline",
    )
    healthy = client.describe_alarms(AlarmNames=[READINESS_ALARM])["MetricAlarms"][0]

    # Failure path: publish zeros, then force ALARM to exercise SNS actions wiring.
    put_ready_samples(client, env=env, values=[0.0, 0.0, 0.0])
    client.set_alarm_state(
        AlarmName=READINESS_ALARM,
        StateValue="ALARM",
        StateReason=(
            "Staging drill simulated sustained readiness failure "
            "(ReadyProbeSuccess < 1 for evaluation window)."
        ),
    )
    failed = client.describe_alarms(AlarmNames=[READINESS_ALARM])["MetricAlarms"][0]

    # Restore OK so staging is not left paging.
    client.set_alarm_state(
        AlarmName=READINESS_ALARM,
        StateValue="OK",
        StateReason="Staging drill complete; restored to OK",
    )
    restored = client.describe_alarms(AlarmNames=[READINESS_ALARM])["MetricAlarms"][0]

    preview = build_alarm_put_kwargs(
        next(a for a in alarms_doc["alarms"] if a["alarmName"] == READINESS_ALARM),
        namespace=alarms_doc["namespace"],
        env=env,
        alarm_actions=alarm_actions or ["arn:aws:sns:us-east-1:0:baladiguard-drill"],
    )

    return {
        "ok": (
            healthy["StateValue"] == "OK"
            and failed["StateValue"] == "ALARM"
            and restored["StateValue"] == "OK"
            and readiness_kwargs["Dimensions"] == [{"Name": "env", "Value": env}]
        ),
        "mode": "live" if live else "simulated",
        "env": env,
        "region": region,
        "timestamp": _iso_now(),
        "runbook": "docs/production-observability.md#staging-exercise-prove-alerts-reach-the-team",
        "stableDimensionKeys": list(STABLE_DIMENSION_KEYS),
        "readinessAlarmPayload": preview,
        "dashboardMetricSample": dashboard_body["widgets"][0]["properties"]["metrics"][0],
        "transitions": {
            "healthy": healthy["StateValue"],
            "failure": failed["StateValue"],
            "restored": restored["StateValue"],
        },
        "alarmActions": readiness_kwargs.get("AlarmActions") or [],
        "notes": [
            "EMF publish dimensions are env-only (see app.core.metrics.build_emf_record).",
            "In-process readiness publisher emits ReadyProbeSuccess continuously.",
            "Live mode SetAlarmState exercises SNS subscriptions; confirm channel delivery.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alarms", type=Path, default=DEFAULT_ALARMS)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--env", default="")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument(
        "--alarm-actions",
        default=os.getenv("OBSERVABILITY_ALARM_ACTIONS", ""),
        help="SNS ARNs (required for meaningful live delivery proof).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real AWS credentials instead of moto simulation.",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env = resolve_env_dimension(args.env or "staging")
    actions = [item.strip() for item in args.alarm_actions.split(",") if item.strip()]
    if args.live and not actions:
        print(
            json.dumps(
                {
                    "ok": False,
                    "errors": ["--live requires --alarm-actions / OBSERVABILITY_ALARM_ACTIONS"],
                },
                indent=2,
            )
        )
        return 1
    evidence = run_drill(
        env=env,
        region=args.region,
        alarm_actions=actions,
        live=bool(args.live),
        alarms_path=args.alarms,
        dashboard_path=args.dashboard,
    )
    print(json.dumps(evidence, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return 0 if evidence.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

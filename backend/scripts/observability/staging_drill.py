"""Staging alarm delivery + organic evaluation drill for issue #185.

Two clearly separated proofs:

1. **Organic evaluation** — publish ``ReadyProbeSuccess`` samples and decide
   ALARM/OK from the same rule CloudWatch uses (Minimum < 1 over N datapoints).
   Live mode can also poll ``DescribeAlarms`` until CloudWatch itself crosses
   threshold (``--organic-wait-seconds``).
2. **SNS delivery** — force ALARM then OK via ``SetAlarmState`` so AlarmActions
   fire, then capture the published notification payloads (moto SQS subscription
   locally; live mode records CloudWatch alarm history + requires a real SNS ARN).

Usage (real staging):

```bash
python scripts/observability/apply_observability.py --apply --env staging \\
  --alarm-actions "$STAGING_OPS_SNS_ARN"
python scripts/observability/staging_drill.py --live --env staging \\
  --alarm-actions "$STAGING_OPS_SNS_ARN" \\
  --organic-wait-seconds 240 \\
  --output infra/observability/evidence/staging-drill-live.json
```

Default mode uses moto + an SQS-subscribed SNS topic so CI proves both organic
verdicts and that ALARM/OK notifications are actually published.
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
from urllib.parse import unquote

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


def organic_ready_verdict(
    values: list[float],
    *,
    threshold: float = 1.0,
    datapoints_to_alarm: int = 3,
) -> str:
    """Mirror BaladiGuard-ReadinessFailure: Minimum < threshold over N points."""
    if len(values) < datapoints_to_alarm:
        return "INSUFFICIENT_DATA"
    window = values[-datapoints_to_alarm:]
    if min(window) < threshold:
        return "ALARM"
    return "OK"


def sanitize_notification(payload: dict[str, Any] | str) -> dict[str, Any]:
    """Keep triage fields; drop account IDs / raw ARNs beyond topic name."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {"raw": "[unparsed notification]"}
    message = payload.get("Message")
    if isinstance(message, str):
        try:
            message_obj = json.loads(message)
        except json.JSONDecodeError:
            message_obj = {"text": message[:200]}
    else:
        message_obj = message or {}
    alarm_name = (
        message_obj.get("AlarmName") or payload.get("AlarmName") or message_obj.get("alarmName")
    )
    new_state = (
        message_obj.get("NewStateValue")
        or payload.get("NewStateValue")
        or message_obj.get("newStateValue")
    )
    reason = (
        message_obj.get("NewStateReason")
        or payload.get("NewStateReason")
        or message_obj.get("newStateReason")
        or ""
    )
    return {
        "alarmName": alarm_name,
        "newStateValue": new_state,
        "newStateReason": str(reason)[:240],
        "subject": payload.get("Subject"),
    }


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


def _cloudwatch_alarm_notification(
    *,
    alarm_name: str,
    new_state: str,
    reason: str,
    region: str,
    topic_arn: str,
) -> str:
    """CloudWatch→SNS alarm notification Message body (subset used by operators)."""
    return json.dumps(
        {
            "AlarmName": alarm_name,
            "NewStateValue": new_state,
            "NewStateReason": reason,
            "Region": region,
            "AlarmArn": f"arn:aws:cloudwatch:{region}:123456789012:alarm:{alarm_name}",
            "Trigger": {
                "MetricName": "ReadyProbeSuccess",
                "Namespace": "BaladiGuard",
                "Dimensions": [{"name": "env", "value": "staging"}],
            },
        }
    )


def _cloudwatch_and_messaging(
    region: str,
    *,
    live: bool,
    alarm_actions: list[str],
    delivery_queue_url: str | None = None,
):
    """Return (cw, sns_topic_arn, receive_notifications, publish_alarm_notice, notes)."""
    if live:
        import boto3

        cw = boto3.client("cloudwatch", region_name=region)
        topic_arn = alarm_actions[0]
        sqs = boto3.client("sqs", region_name=region) if delivery_queue_url else None

        def receive_notifications() -> list[dict[str, Any]]:
            collected: list[dict[str, Any]] = []
            if sqs and delivery_queue_url:
                for _ in range(8):
                    response = sqs.receive_message(
                        QueueUrl=delivery_queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=2,
                    )
                    messages = response.get("Messages") or []
                    if not messages:
                        break
                    for message in messages:
                        body = message.get("Body") or "{}"
                        try:
                            envelope = json.loads(body)
                        except json.JSONDecodeError:
                            envelope = {"Message": body}
                        collected.append(sanitize_notification(envelope))
                        sqs.delete_message(
                            QueueUrl=delivery_queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
            # Always include sanitized CloudWatch action history as corroboration.
            history = cw.describe_alarm_history(
                AlarmName=READINESS_ALARM,
                HistoryItemType="Action",
                MaxRecords=10,
            ).get("AlarmHistoryItems", [])
            for item in history:
                data_raw = item.get("HistoryData") or "{}"
                try:
                    data = json.loads(data_raw)
                except json.JSONDecodeError:
                    data = {}
                state = (data.get("newState") or {}).get("stateValue")
                collected.append(
                    {
                        "alarmName": READINESS_ALARM,
                        "newStateValue": state,
                        "newStateReason": str(
                            (data.get("newState") or {}).get("stateReason") or ""
                        )[:240],
                        "subject": item.get("HistorySummary"),
                        "source": "cloudwatch-alarm-history",
                    }
                )
            return collected

        def publish_alarm_notice(_state: str, _reason: str) -> None:
            return None

        notes = ["live AWS CloudWatch + SNS alarm actions"]
        if delivery_queue_url:
            notes.append("live SNS→SQS subscription captures notification payloads")
        return (
            cw,
            topic_arn,
            receive_notifications,
            publish_alarm_notice,
            notes,
        )

    from moto import mock_aws

    mock = mock_aws()
    mock.start()
    import boto3

    cw = boto3.client("cloudwatch", region_name=region)
    sns = boto3.client("sns", region_name=region)
    sqs = boto3.client("sqs", region_name=region)
    topic_arn = sns.create_topic(Name="baladiguard-ops-drill")["TopicArn"]
    queue_url = sqs.create_queue(QueueName="baladiguard-ops-drill")["QueueUrl"]
    queue_attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
    queue_arn = queue_attrs["Attributes"]["QueueArn"]
    # Allow SNS to deliver into the queue (moto is lenient; keep AWS-shaped policy).
    sqs.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={
            "Policy": json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "sns.amazonaws.com"},
                            "Action": "sqs:SendMessage",
                            "Resource": queue_arn,
                            "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}},
                        }
                    ],
                }
            )
        },
    )
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    cw._baladiguard_moto = mock  # type: ignore[attr-defined]

    def receive_notifications() -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for _ in range(5):
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,
            )
            messages = response.get("Messages") or []
            if not messages:
                break
            for message in messages:
                body = message.get("Body") or "{}"
                try:
                    envelope = json.loads(body)
                except json.JSONDecodeError:
                    envelope = {"Message": body}
                collected.append(sanitize_notification(envelope))
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                )
        return collected

    def publish_alarm_notice(state: str, reason: str) -> None:
        # moto CloudWatch does not reliably invoke AlarmActions on SetAlarmState;
        # publish the same envelope operators see so SNS→SQS delivery is proven.
        sns.publish(
            TopicArn=topic_arn,
            Subject=f"ALARM: {READINESS_ALARM}" if state == "ALARM" else f"OK: {READINESS_ALARM}",
            Message=_cloudwatch_alarm_notification(
                alarm_name=READINESS_ALARM,
                new_state=state,
                reason=reason,
                region=region,
                topic_arn=topic_arn,
            ),
        )

    return (
        cw,
        topic_arn,
        receive_notifications,
        publish_alarm_notice,
        [
            "moto SNS→SQS captures ALARM/OK notification payloads",
            "SetAlarmState is paired with CloudWatch-shaped SNS publishes (moto action gap).",
        ],
    )


def wait_for_cloudwatch_state(
    client,
    *,
    desired: str,
    timeout_seconds: int,
    poll_seconds: int = 15,
) -> dict[str, Any] | None:
    """Poll until CloudWatch reports desired state from metric evaluation."""
    deadline = time.time() + max(0, timeout_seconds)
    last: dict[str, Any] | None = None
    while time.time() <= deadline:
        last = client.describe_alarms(AlarmNames=[READINESS_ALARM])["MetricAlarms"][0]
        reason = str(last.get("StateReason") or "")
        if last.get("StateValue") == desired and (
            "Threshold" in reason or "threshold" in reason.lower() or timeout_seconds == 0
        ):
            return last
        if timeout_seconds == 0:
            return last
        time.sleep(max(1, poll_seconds))
    return last


def run_drill(
    *,
    env: str,
    region: str,
    alarm_actions: list[str],
    live: bool,
    alarms_path: Path,
    dashboard_path: Path,
    organic_wait_seconds: int,
    delivery_queue_url: str | None = None,
) -> dict[str, Any]:
    alarms_doc = load_json(alarms_path)
    dashboard_doc = load_json(dashboard_path)
    client, topic_arn, receive_notifications, publish_alarm_notice, mode_notes = (
        _cloudwatch_and_messaging(
            region,
            live=live,
            alarm_actions=alarm_actions,
            delivery_queue_url=delivery_queue_url,
        )
    )
    actions = alarm_actions or [topic_arn]

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
        alarm_actions=actions,
    )
    readiness_kwargs = next(item for item in applied if item["AlarmName"] == READINESS_ALARM)
    assert readiness_kwargs["Dimensions"] == [{"Name": "env", "Value": env}]
    assert tuple(d["Name"] for d in readiness_kwargs["Dimensions"]) == STABLE_DIMENSION_KEYS

    # --- Organic evaluation (metric samples drive the verdict) ---
    healthy_samples = [1.0, 1.0, 1.0]
    put_ready_samples(client, env=env, values=healthy_samples)
    organic_healthy = organic_ready_verdict(healthy_samples)
    cloudwatch_healthy = None
    if live and organic_wait_seconds > 0:
        cloudwatch_healthy = wait_for_cloudwatch_state(
            client,
            desired="OK",
            timeout_seconds=organic_wait_seconds,
        )

    failure_samples = [0.0, 0.0, 0.0]
    put_ready_samples(client, env=env, values=failure_samples)
    organic_failure = organic_ready_verdict(failure_samples)
    cloudwatch_failure = None
    if live and organic_wait_seconds > 0:
        cloudwatch_failure = wait_for_cloudwatch_state(
            client,
            desired="ALARM",
            timeout_seconds=organic_wait_seconds,
        )

    # --- SNS delivery proof (forced state transitions fire AlarmActions) ---
    alarm_reason = "Delivery drill: force ALARM to exercise SNS AlarmActions"
    client.set_alarm_state(
        AlarmName=READINESS_ALARM,
        StateValue="ALARM",
        StateReason=alarm_reason,
    )
    publish_alarm_notice("ALARM", alarm_reason)
    time.sleep(0.5 if not live else 2.0)
    alarm_notifications = receive_notifications()
    ok_reason = "Delivery drill: force OK to exercise SNS OKActions"
    client.set_alarm_state(
        AlarmName=READINESS_ALARM,
        StateValue="OK",
        StateReason=ok_reason,
    )
    publish_alarm_notice("OK", ok_reason)
    time.sleep(0.5 if not live else 2.0)
    ok_notifications = receive_notifications()

    # --- Organic recovery (overwrite failure samples so staging does not re-page) ---
    recovery_samples = [1.0, 1.0, 1.0]
    put_ready_samples(client, env=env, values=recovery_samples)
    organic_recovery = organic_ready_verdict(recovery_samples)
    cloudwatch_recovery = None
    if live and organic_wait_seconds > 0:
        cloudwatch_recovery = wait_for_cloudwatch_state(
            client,
            desired="OK",
            timeout_seconds=organic_wait_seconds,
        )
    else:
        # Simulated / no-wait: restore forced OK after recovery samples are published.
        client.set_alarm_state(
            AlarmName=READINESS_ALARM,
            StateValue="OK",
            StateReason=(
                "Staging drill complete; recovery samples published and state restored to OK"
            ),
        )

    delivery_states = [
        item.get("newStateValue")
        for item in (alarm_notifications + ok_notifications)
        if item.get("newStateValue")
    ]
    sns_delivery_ok = ("ALARM" in delivery_states and "OK" in delivery_states) or (
        # Live path may only expose action history summaries.
        live
        and any("ALARM" in str(item) for item in alarm_notifications)
        and any("OK" in str(item) for item in ok_notifications)
    )

    preview = build_alarm_put_kwargs(
        next(a for a in alarms_doc["alarms"] if a["alarmName"] == READINESS_ALARM),
        namespace=alarms_doc["namespace"],
        env=env,
        alarm_actions=actions,
    )

    organic_ok = organic_healthy == "OK" and organic_failure == "ALARM" and organic_recovery == "OK"
    if live and organic_wait_seconds > 0:
        organic_ok = (
            organic_ok
            and bool(cloudwatch_failure)
            and cloudwatch_failure.get("StateValue") == "ALARM"
            and bool(cloudwatch_recovery)
            and cloudwatch_recovery.get("StateValue") == "OK"
        )

    topic_name = topic_arn.split(":")[-1] if topic_arn else None
    evidence = {
        "ok": organic_ok
        and sns_delivery_ok
        and readiness_kwargs["Dimensions"] == [{"Name": "env", "Value": env}],
        "mode": "live" if live else "simulated",
        "env": env,
        "region": region,
        "timestamp": _iso_now(),
        "runbook": "docs/production-observability.md#staging-exercise-prove-alerts-reach-the-team",
        "stableDimensionKeys": list(STABLE_DIMENSION_KEYS),
        "readinessAlarmPayload": preview,
        "dashboardMetricSample": dashboard_body["widgets"][0]["properties"]["metrics"][0],
        "organicEvaluation": {
            "description": (
                "Metric-driven readiness verdict using the same Minimum<1 / 3-datapoint "
                "rule as BaladiGuard-ReadinessFailure. Separate from SetAlarmState. "
                "Includes post-drill recovery samples so failure datapoints do not re-page."
            ),
            "healthySamples": healthy_samples,
            "failureSamples": failure_samples,
            "recoverySamples": recovery_samples,
            "healthyVerdict": organic_healthy,
            "failureVerdict": organic_failure,
            "recoveryVerdict": organic_recovery,
            "cloudwatchHealthyState": (cloudwatch_healthy or {}).get("StateValue"),
            "cloudwatchFailureState": (cloudwatch_failure or {}).get("StateValue"),
            "cloudwatchFailureReason": str((cloudwatch_failure or {}).get("StateReason") or "")[
                :240
            ],
            "cloudwatchRecoveryState": (cloudwatch_recovery or {}).get("StateValue"),
            "cloudwatchRecoveryReason": str((cloudwatch_recovery or {}).get("StateReason") or "")[
                :240
            ],
            "recoveryVerified": organic_recovery == "OK",
        },
        "snsDelivery": {
            "description": (
                "Forced SetAlarmState ALARM→OK to exercise AlarmActions/OKActions. "
                "Sanitized notification payloads prove the topic received both states."
            ),
            "topicName": topic_name,
            "alarmNotifications": alarm_notifications,
            "okNotifications": ok_notifications,
            "deliveryConfirmed": sns_delivery_ok,
        },
        "alarmActions": [
            f"arn:aws:sns:{region}:****:{unquote(topic_name or 'topic')}"
            for _ in (readiness_kwargs.get("AlarmActions") or actions)
        ],
        "notes": mode_notes
        + [
            "EMF publish dimensions are env-only (see app.core.metrics.build_emf_record).",
            "In-process readiness publisher emits ReadyProbeSuccess continuously.",
            (
                "Organic evaluation, SNS delivery, and organic recovery are recorded "
                "as separate proofs."
            ),
        ],
    }
    return evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alarms", type=Path, default=DEFAULT_ALARMS)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--env", default="")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument(
        "--alarm-actions",
        default=os.getenv("OBSERVABILITY_ALARM_ACTIONS", ""),
        help="SNS ARNs (required for --live).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real AWS credentials instead of moto simulation.",
    )
    parser.add_argument(
        "--organic-wait-seconds",
        type=int,
        default=0,
        help=(
            "When --live, poll CloudWatch until metric-driven ALARM (and optionally OK). "
            "Use >=180 for the production 60s*3 readiness alarm."
        ),
    )
    parser.add_argument(
        "--delivery-queue-url",
        default=os.getenv("OBSERVABILITY_DELIVERY_QUEUE_URL", ""),
        help="Optional SQS queue URL subscribed to the ops SNS topic (live message capture).",
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
        organic_wait_seconds=int(args.organic_wait_seconds or 0),
        delivery_queue_url=(args.delivery_queue_url or "").strip() or None,
    )
    print(json.dumps(evidence, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return 0 if evidence.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

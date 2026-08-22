#!/usr/bin/env python3
"""Promote one immutable backend image to ECS, with migration-first rollback."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TASK_DEFINITION_FIELDS = {
    "family", "taskRoleArn", "executionRoleArn", "networkMode", "containerDefinitions",
    "volumes", "placementConstraints", "requiresCompatibilities", "cpu", "memory",
    "pidMode", "ipcMode", "proxyConfiguration", "inferenceAccelerators",
    "ephemeralStorage", "runtimePlatform",
}


def aws(*args: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["aws", *args, "--output", "json"], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "unknown AWS CLI error").strip()
        raise RuntimeError(f"AWS {' '.join(args[:2])} failed: {detail}") from error
    return json.loads(result.stdout or "{}")


def next_task_definition(current: dict[str, Any], image: str, version: str) -> dict[str, Any]:
    payload = copy.deepcopy(
        {key: value for key, value in current.items() if key in TASK_DEFINITION_FIELDS}
    )
    containers = payload["containerDefinitions"]
    if len(containers) != 1:
        raise ValueError("BaladiGuard task definitions must contain exactly one container")
    containers[0]["image"] = image
    environment = {item["name"]: item["value"] for item in containers[0].get("environment", [])}
    environment["APP_VERSION"] = version
    containers[0]["environment"] = [
        {"name": key, "value": environment[key]} for key in sorted(environment)
    ]
    return payload


def register(family: str, image: str, version: str) -> tuple[str, str]:
    """Register a new task definition revision and return (previous_running_arn, new_arn).

    The "previous" ARN is read from the ECS service that runs this family so that
    rollback restores the actually-running revision, not the family tip (which may
    already point to a bad image pushed by Terraform).
    """
    current = aws("ecs", "describe-task-definition", "--task-definition", family)["taskDefinition"]
    payload = next_task_definition(current, image, version)
    registered = aws("ecs", "register-task-definition", "--cli-input-json", json.dumps(payload))
    return current["taskDefinitionArn"], registered["taskDefinition"]["taskDefinitionArn"]


def running_task_definition_arns(
    cluster: str, services: list[str], *, healthy_only: bool = False
) -> dict[str, str]:
    """Return service task definitions, optionally only established running releases."""
    if not services:
        return {}
    described = aws(
        "ecs", "describe-services", "--cluster", cluster, "--services", *services,
    )
    result: dict[str, str] = {}
    for svc in described.get("services", []):
        name = svc["serviceName"]
        td_arn = svc.get("taskDefinition")
        if td_arn and (not healthy_only or svc.get("runningCount", 0) > 0):
            result[name] = td_arn
    # An initial deployment has no previous healthy task definition to restore.
    # It must still be allowed to promote the first immutable application image.
    missing = [] if healthy_only else sorted(set(services) - set(result))
    if missing:
        failures = described.get("failures", [])
        details = "; ".join(
            f"{failure.get('arn', 'unknown')}: {failure.get('reason', 'unknown')}"
            for failure in failures
        )
        suffix = f" ({details})" if details else ""
        raise RuntimeError(
            f"could not determine the running task definition for: {', '.join(missing)}{suffix}"
        )
    return result


def run_migration(task_definition: str, cluster: str, subnets: str, security_group: str) -> None:
    configuration = (
        f"awsvpcConfiguration={{subnets=[{subnets}],securityGroups=[{security_group}],"
        "assignPublicIp=ENABLED}"
    )
    response = aws(
        "ecs", "run-task", "--cluster", cluster, "--task-definition", task_definition,
        "--launch-type", "FARGATE", "--network-configuration", configuration,
        "--started-by", "baladiguard-cd",
    )
    failures = response.get("failures", [])
    tasks = response.get("tasks", [])
    if failures:
        reasons = "; ".join(f"{f.get('arn', 'unknown')}: {f.get('reason', 'unknown')}" for f in failures)
        raise RuntimeError(f"run-task failed to place migration task: {reasons}")
    if not tasks:
        raise RuntimeError("run-task returned no tasks and no failures — capacity, networking, or IAM issue")
    task_arn = tasks[0]["taskArn"]
    subprocess.run(
        ["aws", "ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", task_arn],
        check=True,
    )
    stopped = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn)["tasks"][0]
    containers = stopped.get("containers", [])
    if not containers:
        raise RuntimeError(
            f"migration task stopped with no containers: {stopped.get('stoppedReason') or 'unknown'}"
        )
    container = containers[0]
    if container.get("exitCode") != 0:
        raise RuntimeError(
            f"migration failed: {container.get('reason') or stopped.get('stoppedReason') or 'unknown'}"
        )


def update_service(cluster: str, service: str, task_definition: str) -> None:
    aws(
        "ecs", "update-service", "--cluster", cluster, "--service", service,
        "--task-definition", task_definition, "--force-new-deployment",
    )


def _format_service_events(events: list[dict[str, Any]], *, limit: int = 8) -> str:
    if not events:
        return "no recent events"
    lines = []
    for event in events[:limit]:
        when = event.get("createdAt", "?")
        message = (event.get("message") or "").strip()
        lines.append(f"{when}: {message}")
    return "; ".join(lines)


def _format_stopped_task(task: dict[str, Any]) -> str:
    containers = task.get("containers") or []
    container_reasons = ", ".join(
        f"{container.get('name', 'container')}: "
        f"{container.get('reason') or container.get('exitCode', 'unknown')}"
        for container in containers
    ) or "no container details"
    return (
        f"{task.get('taskArn', 'unknown-task')} "
        f"stoppedReason={task.get('stoppedReason') or 'unknown'}; {container_reasons}"
    )


def collect_stabilization_diagnostics(cluster: str, services: list[str]) -> str:
    """Collect ECS events, stopped-task reasons, and CloudWatch log group names."""
    parts = [
        f"CloudWatch logs: {', '.join(f'/ecs/{cluster}/{service}' for service in services)}"
    ]
    try:
        described = aws("ecs", "describe-services", "--cluster", cluster, "--services", *services)
    except Exception as error:
        parts.append(f"describe-services failed: {error}")
        return " | ".join(parts)

    for service in described.get("services", []):
        name = service.get("serviceName", "unknown")
        parts.append(f"{name} events: {_format_service_events(service.get('events') or [])}")
        for deployment in service.get("deployments") or []:
            parts.append(
                f"{name} deployment status={deployment.get('status')} "
                f"rollout={deployment.get('rolloutState')} "
                f"failedTasks={deployment.get('failedTasks')} "
                f"running={deployment.get('runningCount')}/"
                f"{deployment.get('desiredCount')} "
                f"taskDef={deployment.get('taskDefinition')}"
            )

    for service in services:
        try:
            listed = aws(
                "ecs",
                "list-tasks",
                "--cluster",
                cluster,
                "--service-name",
                service,
                "--desired-status",
                "STOPPED",
            )
            task_arns = listed.get("taskArns") or []
            if not task_arns:
                continue
            stopped = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", *task_arns)
            for task in stopped.get("tasks") or []:
                parts.append(f"{service} stopped task: {_format_stopped_task(task)}")
        except Exception as error:
            parts.append(f"{service} stopped-task lookup failed: {error}")
    return " | ".join(parts)


def wait_stable(cluster: str, services: list[str]) -> None:
    try:
        subprocess.run(
            ["aws", "ecs", "wait", "services-stable", "--cluster", cluster, "--services", *services],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        waiter_output = (error.stderr or error.stdout or str(error)).strip()
        details = collect_stabilization_diagnostics(cluster, services)
        raise RuntimeError(f"services did not stabilize ({waiter_output}). {details}") from error


def verify_promoted(cluster: str, services: list[str], promoted: dict[str, str]) -> None:
    """Fail the release unless every service runs the task definition we promoted.

    The ECS deployment circuit breaker can roll a failed rollout back to the old
    tasks, which makes ``wait services-stable`` succeed on the previous revision.
    Without this check a failed rollout would be recorded as a success in the
    deployment manifest.
    """
    running = running_task_definition_arns(cluster, services)
    mismatched = {
        service: {"expected": promoted[service], "actual": running.get(service)}
        for service in services
        if service in promoted and running.get(service) != promoted[service]
    }
    if mismatched:
        raise RuntimeError(f"services not running the promoted task definitions: {mismatched}")


def readiness(url: str, attempts: int = 12) -> None:
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/health/ready", timeout=10) as response:
                if response.status == 200:
                    return
        except Exception:  # the bounded retry reports one safe final error
            pass
        if attempt + 1 < attempts:
            time.sleep(10)
    raise RuntimeError("readiness endpoint did not return HTTP 200")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    parser.add_argument("--cluster", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--subnets", required=True, help="Comma-separated subnet IDs")
    parser.add_argument("--security-group", required=True)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--manifest", type=Path, default=Path("deployment-manifest.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if "@sha256:" not in args.image:
        raise ValueError("--image must be an immutable digest")
    families = {
        name: f"baladiguard-{args.environment}-{name}"
        for name in ("migration", "api", "ai-worker", "redaction-worker")
    }
    previous: dict[str, str] = {}
    promoted: dict[str, str] = {}
    services = ["api", "ai-worker", "redaction-worker"]
    try:
        # Snapshot the currently-running task definitions BEFORE registering new ones.
        previous = running_task_definition_arns(args.cluster, services, healthy_only=True)
        for name, family in families.items():
            _, promoted[name] = register(family, args.image, args.version)
        run_migration(
            promoted["migration"], args.cluster, args.subnets, args.security_group
        )
        for service in services:
            update_service(args.cluster, service, promoted[service])
        wait_stable(args.cluster, services)
        verify_promoted(args.cluster, services, promoted)
        readiness(args.api_url)
    except Exception:
        rollback_errors: list[str] = []
        for service in services:
            if service in previous:
                try:
                    update_service(args.cluster, service, previous[service])
                except Exception as rollback_error:
                    rollback_errors.append(f"{service}: {rollback_error}")
        if previous:
            try:
                wait_stable(args.cluster, [s for s in services if s in previous])
            except Exception as rollback_error:
                rollback_errors.append(f"wait for rollback: {rollback_error}")
        if rollback_errors:
            print("rollback incomplete: " + "; ".join(rollback_errors), file=sys.stderr)
        raise

    manifest = {
        "environment": args.environment,
        "version": args.version,
        "image": args.image,
        "deployed_at": datetime.now(UTC).isoformat(),
        "previous_task_definitions": previous,
        "task_definitions": promoted,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"deployment failed: {error}", file=sys.stderr)
        sys.exit(1)

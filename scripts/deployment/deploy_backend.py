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
    result = subprocess.run(
        ["aws", *args, "--output", "json"], check=True, capture_output=True, text=True
    )
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
    current = aws("ecs", "describe-task-definition", "--task-definition", family)["taskDefinition"]
    previous = current["taskDefinitionArn"]
    payload = next_task_definition(current, image, version)
    registered = aws("ecs", "register-task-definition", "--cli-input-json", json.dumps(payload))
    return previous, registered["taskDefinition"]["taskDefinitionArn"]


def run_migration(task_definition: str, cluster: str, subnets: str, security_group: str) -> None:
    configuration = (
        f"awsvpcConfiguration={{subnets=[{subnets}],securityGroups=[{security_group}],"
        "assignPublicIp=ENABLED}"
    )
    task = aws(
        "ecs", "run-task", "--cluster", cluster, "--task-definition", task_definition,
        "--launch-type", "FARGATE", "--network-configuration", configuration,
        "--started-by", "baladiguard-cd",
    )["tasks"][0]
    task_arn = task["taskArn"]
    subprocess.run(
        ["aws", "ecs", "wait", "tasks-stopped", "--cluster", cluster, "--tasks", task_arn],
        check=True,
    )
    stopped = aws("ecs", "describe-tasks", "--cluster", cluster, "--tasks", task_arn)["tasks"][0]
    container = stopped.get("containers", [{}])[0]
    if container.get("exitCode") != 0:
        raise RuntimeError(
            f"migration failed: {container.get('reason') or stopped.get('stoppedReason') or 'unknown'}"
        )


def update_service(cluster: str, service: str, task_definition: str) -> None:
    aws(
        "ecs", "update-service", "--cluster", cluster, "--service", service,
        "--task-definition", task_definition, "--force-new-deployment",
    )


def wait_stable(cluster: str, services: list[str]) -> None:
    subprocess.run(
        ["aws", "ecs", "wait", "services-stable", "--cluster", cluster, "--services", *services],
        check=True,
    )


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
        for name, family in families.items():
            previous[name], promoted[name] = register(family, args.image, args.version)
        run_migration(
            promoted["migration"], args.cluster, args.subnets, args.security_group
        )
        for service in services:
            update_service(args.cluster, service, promoted[service])
        wait_stable(args.cluster, services)
        readiness(args.api_url)
    except Exception:
        for service in services:
            if service in previous:
                update_service(args.cluster, service, previous[service])
        if previous:
            wait_stable(args.cluster, [service for service in services if service in previous])
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

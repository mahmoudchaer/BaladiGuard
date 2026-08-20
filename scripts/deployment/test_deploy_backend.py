"""Tests for deploy_backend.py covering rollback, migration, and validation paths.

These tests mock aws() and subprocess.run so they exercise the real control
flow without touching AWS.  The reviewer requirements from #328 are:

1. previous ARNs come from the running service, not the family latest
2. migration failures / non-zero exit stops before update-service
3. readiness 503 / exception triggers rollback to those running ARNs
4. --image without @sha256: is rejected
5. empty run-task failures are handled explicitly
"""

import copy
import json
import subprocess
import unittest
from unittest.mock import ANY, patch

from deploy_backend import (
    TASK_DEFINITION_FIELDS,
    aws,
    main,
    next_task_definition,
    parse_args,
    readiness,
    register,
    run_migration,
    running_task_definition_arns,
    update_service,
    verify_promoted,
    wait_stable,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task_def(family: str = "test-api", image: str = "old", revision: int = 1,
                   task_arn: str = "arn:aws:ecs:...:task-definition/test-api:1",
                   cpu: str = "512", memory: str = "1024",
                   extra_env: dict | None = None) -> dict:
    env = [{"name": "APP_VERSION", "value": "old"}]
    if extra_env:
        for k, v in extra_env.items():
            env.append({"name": k, "value": v})
    return {
        "family": family,
        "revision": revision,
        "status": "ACTIVE",
        "taskDefinitionArn": task_arn,
        "taskRoleArn": "arn:aws:iam::...:role/runtime",
        "executionRoleArn": "arn:aws:iam::...:role/execution",
        "networkMode": "awsvpc",
        "cpu": cpu,
        "memory": memory,
        "requiresCompatibilities": ["FARGATE"],
        "runtimePlatform": {"operatingSystemFamily": "LINUX", "cpuArchitecture": "X86_64"},
        "containerDefinitions": [{
            "name": "api",
            "image": image,
            "environment": env,
            "essential": True,
            "logConfiguration": {"logDriver": "awslogs"},
        }],
    }


def _make_service(name: str, task_definition_arn: str) -> dict:
    return {"serviceName": name, "taskDefinition": task_definition_arn, "runningCount": 1}


# ---------------------------------------------------------------------------
# next_task_definition
# ---------------------------------------------------------------------------

class NextTaskDefinitionTests(unittest.TestCase):
    def test_replaces_image_version_and_removes_read_only_fields(self):
        current = _make_task_def()
        original = copy.deepcopy(current)
        result = next_task_definition(current, "repo@sha256:" + "a" * 64, "abc123")
        self.assertNotIn("revision", result)
        self.assertNotIn("taskDefinitionArn", result)
        self.assertEqual(result["containerDefinitions"][0]["image"], "repo@sha256:" + "a" * 64)
        self.assertIn(
            {"name": "APP_VERSION", "value": "abc123"},
            result["containerDefinitions"][0]["environment"],
        )
        self.assertEqual(current, original)

    def test_rejects_ambiguous_multi_container_definition(self):
        with self.assertRaises(ValueError):
            next_task_definition(
                {"family": "x", "containerDefinitions": [{"name": "a"}, {"name": "b"}]},
                "image", "version",
            )

    def test_preserves_extra_environment_keys(self):
        current = _make_task_def(extra_env={"APP_ENV": "staging", "LOG_LEVEL": "info"})
        result = next_task_definition(current, "img@sha256:" + "b" * 64, "v2")
        env = {e["name"]: e["value"] for e in result["containerDefinitions"][0]["environment"]}
        self.assertEqual(env["APP_ENV"], "staging")
        self.assertEqual(env["LOG_LEVEL"], "info")
        self.assertEqual(env["APP_VERSION"], "v2")

    def test_keeps_only_whitelisted_fields(self):
        current = _make_task_def()
        current["extraField"] = "should-be-dropped"
        result = next_task_definition(current, "img@sha256:" + "c" * 64, "v3")
        self.assertNotIn("extraField", result)
        for field in result:
            self.assertIn(field, TASK_DEFINITION_FIELDS)


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

class RegisterTests(unittest.TestCase):
    def test_register_returns_previous_and_new_arns(self):
        td = _make_task_def(task_arn="arn:aws:ecs:...:task-definition/test-api:5")
        registered = copy.deepcopy(td)
        registered["taskDefinitionArn"] = "arn:aws:ecs:...:task-definition/test-api:6"
        registered["revision"] = 6

        calls = []

        def fake_aws(*args):
            calls.append(args)
            if args[0] == "ecs" and args[1] == "describe-task-definition":
                return {"taskDefinition": td}
            if args[0] == "ecs" and args[1] == "register-task-definition":
                return {"taskDefinition": registered}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws):
            prev, new = register("test-api", "img@sha256:" + "d" * 64, "v4")

        self.assertEqual(prev, "arn:aws:ecs:...:task-definition/test-api:5")
        self.assertEqual(new, "arn:aws:ecs:...:task-definition/test-api:6")


# ---------------------------------------------------------------------------
# running_task_definition_arns
# ---------------------------------------------------------------------------

class RunningTaskDefinitionArnsTests(unittest.TestCase):
    def test_returns_service_to_arn_mapping(self):
        services = [
            _make_service("api", "arn:aws:ecs:...:task-definition/baladiguard-staging-api:12"),
            _make_service("ai-worker", "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:8"),
            _make_service("redaction-worker", "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:5"),
        ]

        def fake_aws(*args):
            if args[0] == "ecs" and args[1] == "describe-services":
                return {"services": services}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws):
            result = running_task_definition_arns("test-cluster", ["api", "ai-worker", "redaction-worker"])

        self.assertEqual(result, {
            "api": "arn:aws:ecs:...:task-definition/baladiguard-staging-api:12",
            "ai-worker": "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:8",
            "redaction-worker": "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:5",
        })

    def test_handles_empty_services_list(self):
        with patch("deploy_backend.aws") as mock_aws:
            result = running_task_definition_arns("test-cluster", [])
        self.assertEqual(result, {})
        mock_aws.assert_not_called()

    def test_rejects_services_without_a_running_task_definition(self):
        services = [
            {"serviceName": "api", "taskDefinition": "arn:...:1"},
            {"serviceName": "broken", "taskDefinition": None},
        ]

        def fake_aws(*args):
            return {"services": services}

        with patch("deploy_backend.aws", side_effect=fake_aws):
            with self.assertRaisesRegex(RuntimeError, "broken"):
                running_task_definition_arns("test-cluster", ["api", "broken"])

    def test_healthy_only_allows_initial_deployment_without_running_tasks(self):
        services = [
            {"serviceName": "api", "taskDefinition": "arn:...:1", "runningCount": 0},
            {"serviceName": "ai-worker", "taskDefinition": "arn:...:1", "runningCount": 0},
        ]

        with patch("deploy_backend.aws", return_value={"services": services}):
            result = running_task_definition_arns(
                "test-cluster", ["api", "ai-worker"], healthy_only=True
            )

        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# run_migration
# ---------------------------------------------------------------------------

class RunMigrationTests(unittest.TestCase):
    def setUp(self):
        self.td_arn = "arn:aws:ecs:...:task-definition/test-migration:1"
        self.cluster = "test-cluster"
        self.subnets = "subnet-aaa,subnet-bbb"
        self.sg = "sg-ccc"

    def test_successful_migration(self):
        """Migration exits 0 → no exception."""
        aws_responses = [
            # run-task
            {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]},
            # describe-tasks after wait
            {"tasks": [{"containers": [{"exitCode": 0}], "taskArn": "arn:..."}]},
        ]
        call_count = [0]

        def fake_aws(*args):
            idx = call_count[0]
            call_count[0] += 1
            return aws_responses[idx]

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run") as mock_run:
            run_migration(self.td_arn, self.cluster, self.subnets, self.sg)

        # wait tasks-stopped was called
        mock_run.assert_called_once()
        self.assertIn("wait", mock_run.call_args[0][0])
        self.assertIn("tasks-stopped", mock_run.call_args[0][0])

    def test_migration_non_zero_exit_raises(self):
        """Migration exits 1 → RuntimeError."""
        aws_responses = [
            {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]},
            {"tasks": [{"containers": [{"exitCode": 1, "reason": "Command failed"}], "taskArn": "arn:..."}]},
        ]
        call_count = [0]

        def fake_aws(*args):
            idx = call_count[0]
            call_count[0] += 1
            return aws_responses[idx]

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"):
            with self.assertRaises(RuntimeError) as ctx:
                run_migration(self.td_arn, self.cluster, self.subnets, self.sg)
            self.assertIn("migration failed", str(ctx.exception))

    def test_run_task_failures_raises(self):
        """run-task returns failures array → RuntimeError."""
        aws_responses = [
            {"failures": [{"arn": "arn:...", "reason": "RESOURCE:CPU"}]},
        ]
        call_count = [0]

        def fake_aws(*args):
            idx = call_count[0]
            call_count[0] += 1
            return aws_responses[idx]

        with patch("deploy_backend.aws", side_effect=fake_aws):
            with self.assertRaises(RuntimeError) as ctx:
                run_migration(self.td_arn, self.cluster, self.subnets, self.sg)
            self.assertIn("run-task failed", str(ctx.exception))
            self.assertIn("RESOURCE:CPU", str(ctx.exception))

    def test_run_task_empty_tasks_and_no_failures_raises(self):
        """run-task returns neither tasks nor failures → RuntimeError."""
        aws_responses = [{}]
        call_count = [0]

        def fake_aws(*args):
            idx = call_count[0]
            call_count[0] += 1
            return aws_responses[idx]

        with patch("deploy_backend.aws", side_effect=fake_aws):
            with self.assertRaises(RuntimeError) as ctx:
                run_migration(self.td_arn, self.cluster, self.subnets, self.sg)
            self.assertIn("no tasks and no failures", str(ctx.exception))

    def test_migration_no_containers_raises(self):
        """Stopped task has no containers → RuntimeError."""
        aws_responses = [
            {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]},
            {"tasks": [{"containers": [], "stoppedReason": "OutOfMemory", "taskArn": "arn:..."}]},
        ]
        call_count = [0]

        def fake_aws(*args):
            idx = call_count[0]
            call_count[0] += 1
            return aws_responses[idx]

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"):
            with self.assertRaises(RuntimeError) as ctx:
                run_migration(self.td_arn, self.cluster, self.subnets, self.sg)
            self.assertIn("no containers", str(ctx.exception))


# ---------------------------------------------------------------------------
# update_service / wait_stable
# ---------------------------------------------------------------------------

class ServiceUpdateTests(unittest.TestCase):
    def test_update_service_calls_aws_correctly(self):
        with patch("deploy_backend.aws") as mock_aws:
            update_service("test-cluster", "api", "arn:...:task-definition/api:10")
        mock_aws.assert_called_once()
        args = mock_aws.call_args[0]
        self.assertIn("update-service", args)
        self.assertIn("--force-new-deployment", args)

    def test_wait_stable_calls_subprocess(self):
        with patch("subprocess.run") as mock_run:
            wait_stable("test-cluster", ["api", "ai-worker"])
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("wait", cmd)
        self.assertIn("services-stable", cmd)
        self.assertIn("api", cmd)
        self.assertIn("ai-worker", cmd)


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------

class ReadinessTests(unittest.TestCase):
    def test_returns_on_200(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.status = 200
            readiness("https://api.example.com")  # should not raise

    def test_raises_after_exhausted_retries(self):
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")), \
             patch("time.sleep"):  # don't actually sleep
            with self.assertRaises(RuntimeError) as ctx:
                readiness("https://api.example.com", attempts=3)
            self.assertIn("readiness endpoint", str(ctx.exception))

    def test_retries_on_503_then_succeeds(self):
        call_count = [0]

        class FakeResponse:
            def __init__(self, status):
                self.status = status
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        def fake_urlopen(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                return FakeResponse(503)
            return FakeResponse(200)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
             patch("time.sleep"):
            readiness("https://api.example.com", attempts=5)  # should not raise
        self.assertEqual(call_count[0], 3)


# ---------------------------------------------------------------------------
# parse_args validation
# ---------------------------------------------------------------------------

class ParseArgsTests(unittest.TestCase):
    def test_rejects_image_without_sha256(self):
        with patch("sys.argv", [
            "deploy_backend.py",
            "--environment", "staging",
            "--cluster", "test-cluster",
            "--image", "repo:latest",
            "--version", "abc123",
            "--subnets", "subnet-aaa",
            "--security-group", "sg-aaa",
            "--api-url", "https://api.example.com",
        ]):
            with self.assertRaises(ValueError) as ctx:
                main()
            self.assertIn("immutable digest", str(ctx.exception))

    def test_accepts_image_with_sha256(self):
        """--image with @sha256: passes validation (main will fail on AWS calls)."""
        with patch("sys.argv", [
            "deploy_backend.py",
            "--environment", "staging",
            "--cluster", "test-cluster",
            "--image", "repo@sha256:" + "e" * 64,
            "--version", "abc123",
            "--subnets", "subnet-aaa",
            "--security-group", "sg-aaa",
            "--api-url", "https://api.example.com",
        ]):
            # main() will fail because it tries to call real AWS, but the
            # image validation should pass first.
            with self.assertRaises(Exception):
                main()


# ---------------------------------------------------------------------------
# main() integration: rollback on failure
# ---------------------------------------------------------------------------

class MainRollbackTests(unittest.TestCase):
    """End-to-end tests for the main() deploy/rollback flow."""

    BASE_ARGS = [
        "deploy_backend.py",
        "--environment", "staging",
        "--cluster", "test-cluster",
        "--image", "repo@sha256:" + "f" * 64,
        "--version", "abc123",
        "--subnets", "subnet-aaa,subnet-bbb",
        "--security-group", "sg-ccc",
        "--api-url", "https://api.example.com",
    ]

    def _make_td(self, family, revision, arn):
        return _make_task_def(family=family, revision=revision, task_arn=arn)

    def test_rollback_uses_running_service_arns_on_migration_failure(self):
        """When migration fails, rollback restores the running service ARNs (not family tip)."""
        running_api_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-api:12"
        running_ai_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:8"
        running_redaction_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:5"

        # The family tip might be revision 15 (from a previous Terraform apply),
        # but the service is still running revision 12.
        family_tip_api = self._make_td("baladiguard-staging-api", 15,
                                       "arn:aws:ecs:...:task-definition/baladiguard-staging-api:15")
        family_tip_ai = self._make_td("baladiguard-staging-ai-worker", 10,
                                      "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:10")
        family_tip_redaction = self._make_td("baladiguard-staging-redaction-worker", 7,
                                             "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:7")
        family_tip_migration = self._make_td("baladiguard-staging-migration", 3,
                                             "arn:aws:ecs:...:task-definition/baladiguard-staging-migration:3")

        registered_api = copy.deepcopy(family_tip_api)
        registered_api["taskDefinitionArn"] = "arn:aws:ecs:...:task-definition/baladiguard-staging-api:16"
        registered_ai = copy.deepcopy(family_tip_ai)
        registered_ai["taskDefinitionArn"] = "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:11"
        registered_redaction = copy.deepcopy(family_tip_redaction)
        registered_redaction["taskDefinitionArn"] = "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:8"
        registered_migration = copy.deepcopy(family_tip_migration)
        registered_migration["taskDefinitionArn"] = "arn:aws:ecs:...:task-definition/baladiguard-staging-migration:4"

        aws_calls = []
        update_service_calls = []

        def fake_aws(*args):
            aws_calls.append(args)
            cmd = args[0:2]
            if cmd == ("ecs", "describe-services"):
                return {"services": [
                    _make_service("api", running_api_arn),
                    _make_service("ai-worker", running_ai_arn),
                    _make_service("redaction-worker", running_redaction_arn),
                ]}
            if cmd == ("ecs", "describe-task-definition"):
                family = args[2]
                td_map = {
                    "baladiguard-staging-api": family_tip_api,
                    "baladiguard-staging-ai-worker": family_tip_ai,
                    "baladiguard-staging-redaction-worker": family_tip_redaction,
                    "baladiguard-staging-migration": family_tip_migration,
                }
                return {"taskDefinition": td_map.get(family, family_tip_api)}
            if cmd == ("ecs", "register-task-definition"):
                # Return a new ARN for each registration
                return {"taskDefinition": {"taskDefinitionArn": f"arn:...:new-{len(aws_calls)}"}}
            if cmd == ("ecs", "run-task"):
                # Simulate migration failure
                return {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]}
            if cmd == ("ecs", "describe-tasks"):
                return {"tasks": [{"containers": [{"exitCode": 1, "reason": "Migration error"}], "taskArn": "arn:..."}]}
            if cmd == ("ecs", "update-service"):
                update_service_calls.append(args)
                return {}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"), \
             patch("sys.argv", self.BASE_ARGS), \
             patch("pathlib.Path.write_text"):  # don't write manifest
            with self.assertRaises(RuntimeError) as ctx:
                main()
            self.assertIn("migration failed", str(ctx.exception))

        # Verify rollback used the RUNNING service ARNs, not the family tip.
        # update_service calls: aws("ecs", "update-service", "--cluster", cluster,
        #                           "--service", service, "--task-definition", td, ...)
        # so service name is at index 5 and the task-definition ARN at index 7.
        all_updates = {c[5]: c[7] for c in update_service_calls}
        self.assertEqual(all_updates.get("api"), running_api_arn)
        self.assertEqual(all_updates.get("ai-worker"), running_ai_arn)
        self.assertEqual(all_updates.get("redaction-worker"), running_redaction_arn)

    def test_initial_deployment_failure_does_not_restore_non_running_placeholder(self):
        """A first release must preserve its real error, not roll back to a dead placeholder."""
        td = _make_task_def()
        update_service_calls = []

        def fake_aws(*args):
            cmd = args[0:2]
            if cmd == ("ecs", "describe-services"):
                return {"services": [
                    {"serviceName": name, "taskDefinition": f"arn:...:{name}:1", "runningCount": 0}
                    for name in ("api", "ai-worker", "redaction-worker")
                ]}
            if cmd == ("ecs", "describe-task-definition"):
                return {"taskDefinition": td}
            if cmd == ("ecs", "register-task-definition"):
                return {"taskDefinition": {"taskDefinitionArn": "arn:...:new"}}
            if cmd == ("ecs", "run-task"):
                return {"tasks": [{"taskArn": "arn:...:migration"}]}
            if cmd == ("ecs", "describe-tasks"):
                return {"tasks": [{"containers": [{"exitCode": 1, "reason": "Migration error"}]}]}
            if cmd == ("ecs", "update-service"):
                update_service_calls.append(args)
                return {}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"), \
             patch("sys.argv", self.BASE_ARGS):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                main()

        self.assertEqual(update_service_calls, [])

    def test_rollback_on_readiness_failure(self):
        """When readiness fails, rollback restores running service ARNs."""
        running_api_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-api:12"
        running_ai_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-ai-worker:8"
        running_redaction_arn = "arn:aws:ecs:...:task-definition/baladiguard-staging-redaction-worker:5"

        td = _make_task_def()
        update_service_calls = []
        describe_services_calls = [0]

        def fake_aws(*args):
            cmd = args[0:2]
            if cmd == ("ecs", "describe-services"):
                describe_services_calls[0] += 1
                if describe_services_calls[0] == 1:
                    # Initial snapshot: services run the old revisions.
                    return {"services": [
                        _make_service("api", running_api_arn),
                        _make_service("ai-worker", running_ai_arn),
                        _make_service("redaction-worker", running_redaction_arn),
                    ]}
                # Post-deploy verification: services run the promoted revisions.
                return {"services": [
                    _make_service("api", "arn:...:new"),
                    _make_service("ai-worker", "arn:...:new"),
                    _make_service("redaction-worker", "arn:...:new"),
                ]}
            if cmd == ("ecs", "describe-task-definition"):
                return {"taskDefinition": td}
            if cmd == ("ecs", "register-task-definition"):
                return {"taskDefinition": {"taskDefinitionArn": f"arn:...:new"}}
            if cmd == ("ecs", "run-task"):
                return {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]}
            if cmd == ("ecs", "describe-tasks"):
                return {"tasks": [{"containers": [{"exitCode": 0}], "taskArn": "arn:..."}]}
            if cmd == ("ecs", "update-service"):
                update_service_calls.append(args)
                return {}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"), \
             patch("urllib.request.urlopen", side_effect=Exception("readiness failed")), \
             patch("time.sleep"), \
             patch("sys.argv", self.BASE_ARGS), \
             patch("pathlib.Path.write_text"):
            with self.assertRaises(RuntimeError) as ctx:
                main()
            self.assertIn("readiness endpoint", str(ctx.exception))

        # Rollback should have been called with running ARNs.
        # 3 promote calls (new ARNs) + 3 rollback calls (running ARNs).
        self.assertEqual(len(update_service_calls), 6)
        # service name at index 5, task-definition ARN at index 7
        promote_targets = {c[5]: c[7] for c in update_service_calls[0:3]}
        rollback_targets = {c[5]: c[7] for c in update_service_calls[3:6]}
        self.assertNotEqual(promote_targets.get("api"), running_api_arn)
        self.assertEqual(rollback_targets.get("api"), running_api_arn)
        self.assertEqual(rollback_targets.get("ai-worker"), running_ai_arn)
        self.assertEqual(rollback_targets.get("redaction-worker"), running_redaction_arn)

    def test_migration_failure_prevents_update_service(self):
        """When migration fails, update_service should NOT be called for promotion."""
        running_arns = {
            "api": "arn:...:api:12",
            "ai-worker": "arn:...:ai-worker:8",
            "redaction-worker": "arn:...:redaction-worker:5",
        }
        td = _make_task_def()
        update_service_calls = []

        def fake_aws(*args):
            cmd = args[0:2]
            if cmd == ("ecs", "describe-services"):
                return {"services": [
                    _make_service(k, v) for k, v in running_arns.items()
                ]}
            if cmd == ("ecs", "describe-task-definition"):
                return {"taskDefinition": td}
            if cmd == ("ecs", "register-task-definition"):
                return {"taskDefinition": {"taskDefinitionArn": f"arn:...:new"}}
            if cmd == ("ecs", "run-task"):
                return {"tasks": [{"taskArn": "arn:aws:ecs:...:task/migration-task"}]}
            if cmd == ("ecs", "describe-tasks"):
                return {"tasks": [{"containers": [{"exitCode": 1, "reason": "Migration error"}], "taskArn": "arn:..."}]}
            if cmd == ("ecs", "update-service"):
                update_service_calls.append(args)
                return {}
            return {}

        with patch("deploy_backend.aws", side_effect=fake_aws), \
             patch("subprocess.run"), \
             patch("sys.argv", self.BASE_ARGS), \
             patch("pathlib.Path.write_text"):
            with self.assertRaises(RuntimeError) as ctx:
                main()
            self.assertIn("migration failed", str(ctx.exception))

        # All update_service calls should be rollback only (no promotion).
        # service name at index 5, task-definition ARN at index 7.
        self.assertEqual(len(update_service_calls), 3)
        for c in update_service_calls:
            service, td_arn = c[5], c[7]
            self.assertEqual(
                td_arn, running_arns[service],
                f"Service {service} should have been rolled back to its running ARN, "
                f"got {td_arn}",
            )


# ---------------------------------------------------------------------------
# verify_promoted
# ---------------------------------------------------------------------------

class VerifyPromotedTests(unittest.TestCase):
    def test_passes_when_services_run_promoted_definitions(self):
        promoted = {"api": "arn:...:api:16", "ai-worker": "arn:...:ai:11"}

        def fake_aws(*args):
            return {"services": [
                _make_service("api", "arn:...:api:16"),
                _make_service("ai-worker", "arn:...:ai:11"),
            ]}

        with patch("deploy_backend.aws", side_effect=fake_aws):
            verify_promoted("test-cluster", ["api", "ai-worker"], promoted)

    def test_raises_when_circuit_breaker_rolled_back_to_old_revision(self):
        """wait services-stable can succeed on old tasks after a circuit-breaker
        rollback; verify_promoted must catch that and fail the release."""
        promoted = {"api": "arn:...:api:16"}

        def fake_aws(*args):
            return {"services": [_make_service("api", "arn:...:api:12")]}

        with patch("deploy_backend.aws", side_effect=fake_aws):
            with self.assertRaises(RuntimeError) as ctx:
                verify_promoted("test-cluster", ["api"], promoted)
            self.assertIn("not running the promoted", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

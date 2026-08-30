"""Assert Terraform injects ALLOWED_HOSTS from the API hostname on backend tasks."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF_DIR = ROOT / "infra" / "deployment" / "terraform"
TF_MAIN = TF_DIR / "main.tf"
TF_VARS = TF_DIR / "variables.tf"
STAGING_TFVARS = TF_DIR / "environments" / "staging.tfvars.example"
PRODUCTION_TFVARS = TF_DIR / "environments" / "production.tfvars.example"

BACKEND_TASKS = ("api", "ai-worker", "redaction-worker", "content-safety-worker", "migration")


def _parse_tfvars(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


class TerraformAllowedHostsTests(unittest.TestCase):
    def test_runtime_environment_uses_api_domain_for_allowed_hosts(self) -> None:
        text = TF_MAIN.read_text(encoding="utf-8")
        self.assertIn('{ name = "ALLOWED_HOSTS", value = var.api_domain_name }', text)
        self.assertIn("environment  = local.runtime_environment", text)
        for task in BACKEND_TASKS:
            self.assertIn(task, text)

    def test_allowed_hosts_is_not_a_runtime_secret(self) -> None:
        text = TF_VARS.read_text(encoding="utf-8")
        secrets_block = re.search(
            r'variable "runtime_secret_keys".*?default = \[(.*?)\]',
            text,
            flags=re.S,
        )
        self.assertIsNotNone(secrets_block)
        self.assertNotIn("ALLOWED_HOSTS", secrets_block.group(1))
        for required in (
            "CITIZEN_OTP_DELIVERY_CHANNEL",
            "CITIZEN_OTP_WHATSAPP_ACCESS_TOKEN",
            "CITIZEN_OTP_WHATSAPP_PHONE_NUMBER_ID",
            "CITIZEN_OTP_WHATSAPP_MESSAGE_MODE",
            "NOTIFICATION_ALLOWLIST_PHONES",
        ):
            self.assertIn(required, secrets_block.group(1))

    def test_api_task_role_can_read_ops_cloudwatch(self) -> None:
        text = TF_MAIN.read_text(encoding="utf-8")
        self.assertIn('"cloudwatch:GetMetricData"', text)
        self.assertIn('"cloudwatch:DescribeAlarms"', text)
        self.assertIn('"dynamodb:DescribeContinuousBackups"', text)
        self.assertIn("alarm:BaladiGuard-*", text)

    def test_content_safety_worker_is_wired_like_other_workers(self) -> None:
        text = TF_MAIN.read_text(encoding="utf-8")
        self.assertIn('{ name = "CONTENT_SAFETY_ENABLED", value = "true" }', text)
        self.assertIn('content-safety-worker = ["python", "-m", "app.workers.content_safety_worker"]', text)
        self.assertIn("rekognition:DetectModerationLabels", text)
        self.assertIn('toset(["ai-worker", "redaction-worker", "content-safety-worker"])', text)

    def test_staging_and_production_examples_supply_api_hostnames(self) -> None:
        staging = _parse_tfvars(STAGING_TFVARS)
        production = _parse_tfvars(PRODUCTION_TFVARS)
        self.assertEqual(staging["environment"], "staging")
        self.assertEqual(production["environment"], "production")
        self.assertTrue(staging["api_domain_name"])
        self.assertTrue(production["api_domain_name"])
        self.assertNotEqual(staging["api_domain_name"], production["api_domain_name"])
        self.assertIn("api.", staging["api_domain_name"])
        self.assertIn("api.", production["api_domain_name"])


if __name__ == "__main__":
    unittest.main()

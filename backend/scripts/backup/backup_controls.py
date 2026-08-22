"""Audit and apply production backup protections for BaladiGuard.

The default operation is read-only. ``--apply`` is required for mutations and
refuses localhost endpoints. Existing DynamoDB tables are protected in place;
the script never creates, deletes, or replaces application tables.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

DEFAULT_TABLE_SUFFIXES = (
    "tickets",
    "users",
    "phone-claims",
    "photo-upload-claims",
    "citizen-otp-challenges",
    "citizen-sessions",
    "staff-users",
    "staff-username-claims",
    "staff-password-reset-challenges",
    "ticket-status-history",
    "ticket-audit-history",
    "staff-comments",
    "account-audit",
    "notification-deliveries",
    "notification-claims",
    "ticket-submission-claims",
    "ai-outputs",
    "ai-processing-jobs",
    "image-redaction-jobs",
    "duplicate-groups",
    "municipalities",
    "departments",
    "workforce-workers",
    "workforce-teams",
    "categories",
    "counters",
    "rate-limit-buckets",
    "ops-alert-acks",
    "ops-error-groups",
    "ops-audit",
    "privacy-request-audit",
)


def _settings() -> tuple[str, str, str | None]:
    region = os.getenv("AWS_REGION", "us-east-1").strip()
    prefix = os.getenv("DYNAMODB_TABLE_PREFIX", "baladiguard-").strip()
    endpoint = os.getenv("DYNAMODB_ENDPOINT_URL", "").strip() or None
    return region, prefix, endpoint


def _clients(region: str, endpoint: str | None):
    kwargs: dict[str, Any] = {"region_name": region}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("dynamodb", **kwargs), boto3.client("s3", **kwargs)


def _s3_lifecycle() -> dict[str, Any]:
    return {
        "Rules": [
            {
                "ID": "ReportPhotoVersionRetention",
                "Status": "Enabled",
                "Filter": {"Prefix": "reports/photos/"},
                "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            },
            {
                "ID": "OrphanReportPhotoCleanup",
                "Status": "Enabled",
                "Filter": {
                    "And": {
                        "Prefix": "reports/photos/v2/",
                        "Tags": [{"Key": "upload-state", "Value": "orphan"}],
                    }
                },
                "Expiration": {"Days": 2},
            },
            {
                "ID": "RedactedDerivativeVersionRetention",
                "Status": "Enabled",
                "Filter": {"Prefix": "reports/redacted/"},
                "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            },
        ]
    }


def _merged_s3_lifecycle(existing_rules: list[dict[str, Any]]) -> dict[str, Any]:
    desired = _s3_lifecycle()["Rules"]
    desired_ids = {rule["ID"] for rule in desired}
    rules = [rule for rule in existing_rules if rule.get("ID") not in desired_ids]
    rules.extend(desired)
    return {"Rules": rules}


def audit(dynamodb, s3, prefix: str, bucket: str) -> dict[str, Any]:
    tables = []
    existing = set(dynamodb.list_tables().get("TableNames", []))
    for suffix in DEFAULT_TABLE_SUFFIXES:
        name = f"{prefix}{suffix}"
        if name not in existing:
            tables.append({"table": name, "exists": False, "pitr": False})
            continue
        status = dynamodb.describe_continuous_backups(TableName=name)
        pitr = status["ContinuousBackupsDescription"].get("PointInTimeRecoveryDescription", {})
        tables.append(
            {
                "table": name,
                "exists": True,
                "pitr": pitr.get("PointInTimeRecoveryStatus") == "ENABLED",
            }
        )

    versioning = s3.get_bucket_versioning(Bucket=bucket).get("Status") == "Enabled"
    try:
        encryption = s3.get_bucket_encryption(Bucket=bucket).get(
            "ServerSideEncryptionConfiguration", {}
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {
            "ServerSideEncryptionConfigurationNotFoundError",
            "NoSuchBucket",
        }:
            raise
        encryption = {}
    try:
        public_block = s3.get_public_access_block(Bucket=bucket).get(
            "PublicAccessBlockConfiguration", {}
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {
            "NoSuchPublicAccessBlockConfiguration",
            "NoSuchBucket",
        }:
            raise
        public_block = {}
    try:
        lifecycle = s3.get_bucket_lifecycle_configuration(Bucket=bucket).get("Rules", [])
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"NoSuchLifecycleConfiguration", "NoSuchBucket"}:
            raise
        lifecycle = []
    return {
        "checkedAt": datetime.now(UTC).isoformat(),
        "bucket": bucket,
        "dynamodb": tables,
        "s3": {
            "versioning": versioning,
            "encryption": bool(encryption.get("Rules")),
            "publicAccessBlock": all(
                public_block.get(k, False)
                for k in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            ),
            "lifecycleRules": len(lifecycle),
            "photoLifecycle": any(
                rule.get("ID") == "ReportPhotoVersionRetention"
                and rule.get("Status") == "Enabled"
                and rule.get("Filter", {}).get("Prefix") == "reports/photos/"
                and rule.get("NoncurrentVersionExpiration", {}).get("NoncurrentDays") == 90
                for rule in lifecycle
            ),
            "orphanPhotoLifecycle": any(
                rule.get("ID") == "OrphanReportPhotoCleanup"
                and rule.get("Status") == "Enabled"
                and rule.get("Expiration", {}).get("Days") == 2
                for rule in lifecycle
            ),
            "redactedDerivativeLifecycle": any(
                rule.get("ID") == "RedactedDerivativeVersionRetention"
                and rule.get("Status") == "Enabled"
                and rule.get("Filter", {}).get("Prefix") == "reports/redacted/"
                and rule.get("NoncurrentVersionExpiration", {}).get("NoncurrentDays") == 90
                for rule in lifecycle
            ),
        },
    }


def apply(dynamodb, s3, report: dict[str, Any], bucket: str) -> None:
    for item in report["dynamodb"]:
        if item["exists"] and not item["pitr"]:
            dynamodb.update_continuous_backups(
                TableName=item["table"],
                PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True},
            )
    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    try:
        existing_rules = s3.get_bucket_lifecycle_configuration(Bucket=bucket).get("Rules", [])
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
            existing_rules = []
        else:
            raise
    s3.put_bucket_lifecycle_configuration(
        Bucket=bucket, LifecycleConfiguration=_merged_s3_lifecycle(existing_rules)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply missing protections")
    parser.add_argument("--output", type=Path, help="Write the audit JSON to this path")
    args = parser.parse_args()
    region, prefix, endpoint = _settings()
    if args.apply and endpoint:
        raise SystemExit("Refusing to apply production backup controls to a custom endpoint.")
    bucket = os.getenv("AWS_S3_BUCKET", "").strip()
    if not bucket:
        raise SystemExit("AWS_S3_BUCKET must be configured.")
    dynamodb, s3 = _clients(region, endpoint)
    report = audit(dynamodb, s3, prefix, bucket)
    if args.apply:
        apply(dynamodb, s3, report, bucket)
        report = audit(dynamodb, s3, prefix, bucket)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    healthy = all(item["exists"] and item["pitr"] for item in report["dynamodb"])
    healthy = healthy and all(
        report["s3"][key] for key in ("versioning", "encryption", "publicAccessBlock")
    )
    healthy = healthy and all(
        report["s3"][key]
        for key in (
            "photoLifecycle",
            "orphanPhotoLifecycle",
            "redactedDerivativeLifecycle",
        )
    )
    return 0 if healthy else 2


if __name__ == "__main__":
    raise SystemExit(main())

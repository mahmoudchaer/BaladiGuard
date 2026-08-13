"""Restore a DynamoDB table and S3 report photos into isolated targets.

This command requires explicit target names and refuses names that match the
configured production prefix. It never deletes or overwrites an active target.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--target-table", required=True)
    parser.add_argument("--bucket", default=os.getenv("AWS_S3_BUCKET", ""))
    parser.add_argument("--target-prefix", required=True)
    parser.add_argument("--execute", action="store_true", help="Perform the isolated restore")
    args = parser.parse_args()
    production_prefix = os.getenv("DYNAMODB_TABLE_PREFIX", "baladiguard-")
    if args.target_table.startswith(production_prefix) or not args.target_table.endswith(
        "-restore"
    ):
        raise SystemExit(
            "Target table must not start with the production prefix and must end in '-restore' "
            "(for example, isolated-tickets-20260801-restore)."
        )
    if not re.fullmatch(r"[A-Za-z0-9!_.*'()/-]+", args.target_prefix):
        raise SystemExit("Target prefix contains unsupported characters.")
    normalized_prefix = args.target_prefix.rstrip("/")
    if not normalized_prefix.startswith("restore-tests/") and normalized_prefix != "restore-tests":
        raise SystemExit("Target prefix must be inside restore-tests/.")
    if not args.bucket:
        raise SystemExit("AWS_S3_BUCKET or --bucket is required.")

    region = os.getenv("AWS_REGION", "us-east-1")
    dynamodb = boto3.client("dynamodb", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    target_bucket_prefix = f"{args.target_prefix.rstrip('/')}/{run_id}/"
    if not args.execute:
        print(
            json.dumps(
                {
                    "dryRun": True,
                    "runId": run_id,
                    "targetTable": args.target_table,
                    "targetPrefix": target_bucket_prefix,
                },
                indent=2,
            )
        )
        return 0

    try:
        dynamodb.describe_table(TableName=args.target_table)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
    else:
        raise SystemExit("Target table already exists; choose a new isolated target name.")
    restore = dynamodb.restore_table_to_point_in_time(
        SourceTableName=args.source_table,
        TargetTableName=args.target_table,
        UseLatestRestorableTime=True,
    )
    dynamodb.get_waiter("table_exists").wait(TableName=args.target_table)
    deadline = time.monotonic() + 1800
    while True:
        status = dynamodb.describe_table(TableName=args.target_table)["Table"]["TableStatus"]
        if status == "ACTIVE":
            break
        if status in {"DELETING", "ARCHIVING", "INACCESSIBLE_ENCRYPTION_CREDENTIALS"}:
            raise SystemExit(f"Isolated restore entered unexpected status: {status}.")
        if time.monotonic() >= deadline:
            raise SystemExit("Timed out waiting for the isolated restore table to become ACTIVE.")
        time.sleep(5)
    paginator = s3.get_paginator("list_object_versions")
    copied = 0
    for prefix in ("reports/photos/", "reports/redacted/"):
        for page in paginator.paginate(Bucket=args.bucket, Prefix=prefix):
            for version in page.get("Versions", []):
                source = {
                    "Bucket": args.bucket,
                    "Key": version["Key"],
                    "VersionId": version["VersionId"],
                }
                target_key = target_bucket_prefix + version["Key"]
                s3.copy_object(
                    Bucket=args.bucket,
                    Key=target_key,
                    CopySource=source,
                    ServerSideEncryption="AES256",
                )
                copied += 1
    print(
        json.dumps(
            {
                "dryRun": False,
                "runId": run_id,
                "restoreTable": restore["TableDescription"]["TableName"],
                "copiedPhotoVersions": copied,
                "targetPrefix": target_bucket_prefix,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

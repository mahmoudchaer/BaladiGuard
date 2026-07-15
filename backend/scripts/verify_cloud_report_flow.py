"""Verify the real cloud report flow: S3 upload + DynamoDB persist + API read.

Requires cloud configuration (not memory, not DynamoDB Local):
  DATABASE_BACKEND=dynamodb
  DYNAMODB_ENDPOINT_URL empty/unset
  AWS_S3_BUCKET + AWS credentials set

Usage (from backend/):
  python scripts/verify_cloud_report_flow.py

This script intentionally does NOT force DATABASE_BACKEND=memory.
CI unit tests remain on memory/moto; this script proves the cloud path.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Minimal valid JPEG used for the multipart upload.
_MIN_JPEG = bytes(
    [
        0xFF,
        0xD8,
        0xFF,
        0xE0,
        0x00,
        0x10,
        0x4A,
        0x46,
        0x49,
        0x46,
        0x00,
        0x01,
        0x01,
        0x00,
        0x00,
        0x01,
        0x00,
        0x01,
        0x00,
        0x00,
        0xFF,
        0xDB,
        0x00,
        0x43,
        0x00,
        *([0x08] * 64),
        0xFF,
        0xC0,
        0x00,
        0x0B,
        0x08,
        0x00,
        0x01,
        0x00,
        0x01,
        0x01,
        0x01,
        0x11,
        0x00,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x00,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x08,
        0xFF,
        0xC4,
        0x00,
        0x14,
        0x10,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFF,
        0xDA,
        0x00,
        0x08,
        0x01,
        0x01,
        0x00,
        0x00,
        0x3F,
        0x00,
        0x7F,
        0xFF,
        0xD9,
    ]
)


def _require_cloud_settings() -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    if not settings.use_dynamodb:
        raise SystemExit(
            "Cloud verification requires DATABASE_BACKEND=dynamodb "
            "(currently not using DynamoDB)."
        )

    if settings.dynamodb_endpoint_url:
        raise SystemExit(
            "Cloud verification requires DYNAMODB_ENDPOINT_URL to be empty "
            f"(currently {settings.dynamodb_endpoint_url!r}). "
            "Unset it to target real AWS DynamoDB."
        )

    if not settings.aws_s3_bucket:
        raise SystemExit(
            "Cloud verification requires AWS_S3_BUCKET to be set for real photo uploads."
        )


def main() -> int:
    _require_cloud_settings()

    from fastapi.testclient import TestClient

    from app.database.dynamodb import create_dynamodb_resource
    from app.database.dynamodb_tables import build_table_name
    from app.config import get_settings
    from app.main import app
    import boto3

    settings = get_settings()
    client = TestClient(app)

    print("=== 1. Upload photo to real S3 ===")
    upload = client.post(
        "/v1/uploads/report-photo",
        files={"file": ("cloud-flow-check.jpg", _MIN_JPEG, "image/jpeg")},
        headers={"X-Client-Version": "mobile-0.1.0"},
    )
    if upload.status_code != 200:
        print("upload_status", upload.status_code)
        print("upload_body", upload.json())
        return 1

    image_object_key = upload.json()["imageObjectKey"]
    print("imageObjectKey", image_object_key)

    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.head_object(Bucket=settings.aws_s3_bucket, Key=image_object_key)
    print("s3_object_exists", True)

    print("=== 2. Submit ticket to cloud DynamoDB ===")
    submit = client.post(
        "/v1/tickets",
        json={
            "description": "Cloud E2E verification: pothole near AUB main gate.",
            "languageHint": "auto",
            "contact": {
                "name": "Cloud Verify",
                "phone": "+96170123456",
                "preferredChannel": "SMS",
            },
            "location": {
                "latitude": 33.896112,
                "longitude": 35.478419,
                "addressText": "Near AUB Main Gate, Hamra, Beirut",
                "source": "PLACEHOLDER",
            },
            "imageObjectKey": image_object_key,
            "clientMetadata": {"platform": "ios", "appVersion": "0.1.0"},
        },
        headers={
            "Content-Type": "application/json",
            "X-Client-Version": "mobile-0.1.0",
        },
    )
    if submit.status_code != 201:
        print("submit_status", submit.status_code)
        print("submit_body", submit.json())
        return 1

    created = submit.json()
    ticket_id = created["ticketId"]
    print("ticketId", ticket_id)
    print("ticketNumber", created["ticketNumber"])
    print("trackingCode", created["trackingCode"])

    print("=== 3. Retrieve ticket via API ===")
    detail = client.get(f"/v1/tickets/{ticket_id}")
    if detail.status_code != 200:
        print("get_status", detail.status_code)
        print("get_body", detail.json())
        return 1

    body = detail.json()
    if body.get("imageObjectKey") != image_object_key:
        print("imageObjectKey mismatch", body.get("imageObjectKey"), image_object_key)
        return 1
    print("api_imageObjectKey", body["imageObjectKey"])

    listing = client.get("/v1/tickets")
    if listing.status_code != 200:
        print("list_status", listing.status_code)
        return 1
    tickets = listing.json()
    if not any(ticket.get("ticketId") == ticket_id for ticket in tickets):
        print("ticket missing from GET /v1/tickets")
        return 1
    print("listed_in_admin_api", True)

    print("=== 4. Confirm row in cloud DynamoDB ===")
    resource = create_dynamodb_resource()
    table = resource.Table(build_table_name(settings.dynamodb_table_prefix, "tickets"))
    stored = table.get_item(Key={"ticketId": ticket_id}).get("Item")
    if not stored:
        print("ticket not found in DynamoDB table")
        return 1
    if stored.get("imageObjectKey") != image_object_key:
        print("dynamodb imageObjectKey mismatch", stored.get("imageObjectKey"))
        return 1
    print("dynamodb_persisted", True)
    print("dynamodb_endpoint", resource.meta.client.meta.endpoint_url)

    print("CLOUD_REPORT_FLOW_OK")
    print(
        "Admin dashboard check: start admin with VITE_USE_MOCK_DATA unset/false "
        "and open http://localhost:5173 - ticket should appear in the list."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

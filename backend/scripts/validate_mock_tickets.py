"""Validate mock_tickets.json against the StoredTicket persistence model."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.stored_ticket import StoredTicket

path = Path(__file__).resolve().parents[2] / "mock_tickets.json"
records = json.loads(path.read_text(encoding="utf-8"))

print(f"Loaded {len(records)} records from mock_tickets.json\n")

all_keys: set[str] = set()
for record in records:
    all_keys.update(record.keys())
    if "contact" in record:
        all_keys.update(f"contact.{key}" for key in record["contact"])
    if "location" in record:
        all_keys.update(f"location.{key}" for key in record["location"])

schema_fields = {
    "ticketId",
    "ticketNumber",
    "trackingCode",
    "description",
    "originalDescription",
    "cleanedDescription",
    "contact",
    "location",
    "imageObjectKey",
    "ownerUserId",
    "status",
    "category",
    "aiSuggestedCategory",
    "aiCategoryExplanation",
    "aiConfidence",
    "finalCategory",
    "categoryReviewedBy",
    "categoryReviewedAt",
    "aiProcessingStatus",
    "aiModelVersion",
    "publicStatus",
    "publicDescription",
    "publicLocationLabel",
    "publicPublishedAt",
    "priority",
    "urgencyScore",
    "urgencyReason",
    "createdBy",
    "municipalityId",
    "departmentId",
    "duplicateGroupId",
    "createdAt",
    "updatedAt",
    "contact.name",
    "contact.phone",
    "contact.email",
    "location.latitude",
    "location.longitude",
    "location.addressText",
    "location.source",
}

extra = sorted(key for key in all_keys if key not in schema_fields)

print("=== Field coverage vs StoredTicket / docs/database.md Ticket ===")
print(f"Unique keys in mock file: {len(all_keys)}")
print("EXTRA keys (not in schema):", extra or "none")
print()

errors: list[tuple[int, str, ValidationError]] = []
for index, record in enumerate(records, 1):
    try:
        StoredTicket.model_validate(record)
        ticket_id = record["ticketId"]
        status = record["status"]
        category = record["category"]
        print(f"  [{index:2d}] OK  {ticket_id}  status={status}  category={category}")
    except ValidationError as error:
        errors.append((index, record.get("ticketId", "?"), error))

print()
if errors:
    print(f"FAILED: {len(errors)} record(s)")
    for index, ticket_id, error in errors:
        print(f"  Record {index} ({ticket_id}):")
        print(error)
    raise SystemExit(1)

print(f"PASSED: all {len(records)} records validate against StoredTicket\n")

contact_violations = [
    record["ticketId"]
    for record in records
    if not record.get("contact", {}).get("phone") and not record.get("contact", {}).get("email")
]
print("=== Contact rule (phone OR email) ===")
print("Violations:", contact_violations or "none")
if contact_violations:
    raise SystemExit(1)

valid_status = {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED"}
bad_status = [
    (record["ticketId"], record["status"])
    for record in records
    if record["status"] not in valid_status
]
print("\n=== Status enum (uppercase) ===")
print("Invalid:", bad_status or "none")
if bad_status:
    raise SystemExit(1)

bad_ids = [record["ticketId"] for record in records if not record["ticketId"].startswith("tkt_")]
print("\n=== ticketId format (tkt_*) ===")
print("Invalid:", bad_ids or "none")
if bad_ids:
    raise SystemExit(1)

old_keys = {
    "id",
    "created_by",
    "municipality_id",
    "department_id",
    "duplicate_group_id",
    "address",
    "latitude",
    "longitude",
    "created_at",
    "updated_at",
}
found_old = sorted(old_keys & set().union(*(record.keys() for record in records)))
print("\n=== Old snake_case / flat schema keys (should be absent) ===")
print("Found:", found_old or "none")
if found_old:
    raise SystemExit(1)

valid_public_statuses = {"DRAFT", "PUBLISHED", "UNPUBLISHED"}
bad_public_statuses = [
    (record["ticketId"], record.get("publicStatus"))
    for record in records
    if record.get("publicStatus") not in valid_public_statuses
]
print("\n=== Public status enum ===")
print("Invalid:", bad_public_statuses or "none")
if bad_public_statuses:
    raise SystemExit(1)

unsafe_public = [
    record["ticketId"]
    for record in records
    if record.get("publicStatus") == "PUBLISHED"
    and (
        not record.get("publicDescription")
        or not record.get("publicLocationLabel")
        or not record.get("publicPublishedAt")
        or record["location"]["addressText"] == record.get("publicLocationLabel")
    )
]
print("\n=== Published reports have approved public fields ===")
print("Violations:", unsafe_public or "none")
if unsafe_public:
    raise SystemExit(1)

ownerless = [record["ticketId"] for record in records if not record.get("ownerUserId")]
print("\n=== Synthetic citizen ownership ===")
print("Ownerless:", ownerless or "none")
if ownerless:
    raise SystemExit(1)

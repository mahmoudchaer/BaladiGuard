import time
from typing import Any

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_client, create_dynamodb_resource
from app.database.dynamodb_tables import (
    TABLE_DEFINITIONS,
    build_create_table_params,
    build_table_name,
)


def wait_for_table(client, table_name: str) -> None:
    while True:
        description = client.describe_table(TableName=table_name)["Table"]
        if description["TableStatus"] == "ACTIVE":
            return
        time.sleep(0.5)


def create_tables(prefix: str, settings: Settings | None = None) -> list[str]:
    resource = create_dynamodb_resource(settings)
    client = create_dynamodb_client(settings)
    created_tables: list[str] = []

    for definition in TABLE_DEFINITIONS:
        table_name = build_table_name(prefix, definition["suffix"])
        params: dict[str, Any] = build_create_table_params(prefix, definition)
        try:
            resource.create_table(**params)
            print(f"Created table: {table_name}")
            created_tables.append(table_name)
        except ClientError as error:
            if error.response["Error"]["Code"] != "ResourceInUseException":
                raise
            print(f"Table already exists: {table_name}")
            _ensure_missing_gsis(client, table_name, definition)

    for table_name in created_tables:
        wait_for_table(client, table_name)

    # Enable TTL on ephemeral tables. Idempotent.
    rate_limit_table = build_table_name(prefix, "rate-limit-buckets")
    if rate_limit_table not in created_tables:
        wait_for_table(client, rate_limit_table)
    _ensure_ttl(client, rate_limit_table, attribute_name="expiresAt")

    staff_reset_table = build_table_name(prefix, "staff-password-reset-challenges")
    if staff_reset_table not in created_tables:
        wait_for_table(client, staff_reset_table)
    _ensure_ttl(client, staff_reset_table, attribute_name="ttl")

    # Ticket submission idempotency claims (#258): completed rows retain for
    # offline client retries; abandoned claims expire shortly after reclaim window.
    submission_claims_table = build_table_name(prefix, "ticket-submission-claims")
    if submission_claims_table not in created_tables:
        wait_for_table(client, submission_claims_table)
    _ensure_ttl(client, submission_claims_table, attribute_name="ttl")

    whatsapp_conversations = build_table_name(prefix, "whatsapp-conversations")
    if whatsapp_conversations not in created_tables:
        wait_for_table(client, whatsapp_conversations)
    _ensure_ttl(client, whatsapp_conversations, attribute_name="ttl")

    whatsapp_dedup = build_table_name(prefix, "whatsapp-inbound-dedup")
    if whatsapp_dedup not in created_tables:
        wait_for_table(client, whatsapp_dedup)
    _ensure_ttl(client, whatsapp_dedup, attribute_name="ttl")

    # Citizen auth ephemerals (#321): sessions (~30d) and OTP challenges (~5m).
    citizen_sessions = build_table_name(prefix, "citizen-sessions")
    if citizen_sessions not in created_tables:
        wait_for_table(client, citizen_sessions)
    _ensure_ttl(client, citizen_sessions, attribute_name="ttl")

    citizen_otp = build_table_name(prefix, "citizen-otp-challenges")
    if citizen_otp not in created_tables:
        wait_for_table(client, citizen_otp)
    _ensure_ttl(client, citizen_otp, attribute_name="ttl")

    return created_tables


def _ensure_missing_gsis(client, table_name: str, definition: dict[str, Any]) -> None:
    """Add GSIs defined in code but missing on an already-created table."""
    desired = definition.get("global_secondary_indexes") or []
    if not desired:
        return

    wait_for_table(client, table_name)
    description = client.describe_table(TableName=table_name)["Table"]
    existing = {index["IndexName"] for index in description.get("GlobalSecondaryIndexes", []) or []}
    attribute_defs = {
        item["AttributeName"]: item for item in description.get("AttributeDefinitions", [])
    }
    for attr in definition.get("attribute_definitions") or []:
        attribute_defs[attr["AttributeName"]] = attr

    for index in desired:
        name = index["IndexName"]
        if name in existing:
            continue
        print(f"Creating missing GSI on {table_name}: {name}")
        # DynamoDB allows only one GSI create/delete at a time per table.
        wait_for_table(client, table_name)
        client.update_table(
            TableName=table_name,
            AttributeDefinitions=list(attribute_defs.values()),
            GlobalSecondaryIndexUpdates=[
                {
                    "Create": {
                        "IndexName": name,
                        "KeySchema": index["KeySchema"],
                        "Projection": index["Projection"],
                    }
                }
            ],
        )
        _wait_for_gsi(client, table_name, name)
        print(f"GSI ready: {table_name}.{name}")


def _wait_for_gsi(
    client,
    table_name: str,
    index_name: str,
    *,
    timeout_seconds: float = 300,
    poll_seconds: float = 2,
) -> None:
    """Poll until a GSI is ACTIVE, or fail with a bounded timeout / terminal state."""
    deadline = time.monotonic() + timeout_seconds
    last_status: str | None = None
    while True:
        description = client.describe_table(TableName=table_name)["Table"]
        indexes = description.get("GlobalSecondaryIndexes") or []
        match = next((item for item in indexes if item["IndexName"] == index_name), None)
        # DescribeTable is eventually consistent after UpdateTable — a missing match
        # is a transient window, not an immediate failure.
        if match is None:
            last_status = None
        else:
            last_status = match.get("IndexStatus")
            if last_status == "ACTIVE":
                return
            if last_status in {"DELETING"}:
                raise RuntimeError(
                    f"GSI {table_name}.{index_name} entered terminal status {last_status}"
                )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Timed out waiting for GSI {table_name}.{index_name} to become ACTIVE "
                f"(last status={last_status})"
            )
        time.sleep(poll_seconds)


def _ensure_ttl(client, table_name: str, *, attribute_name: str) -> None:
    try:
        client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": attribute_name,
            },
        )
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        # Already enabled / unsupported in some local emulators — non-fatal.
        if code in {"ValidationException", "ResourceNotFoundException"}:
            return
        raise


def delete_tables(prefix: str, settings: Settings | None = None) -> None:
    client = create_dynamodb_client(settings)
    existing_tables = client.list_tables().get("TableNames", [])
    target_tables = [table_name for table_name in existing_tables if table_name.startswith(prefix)]

    for table_name in target_tables:
        print(f"Deleting table: {table_name}")
        client.delete_table(TableName=table_name)

    for table_name in target_tables:
        waiter = client.get_waiter("table_not_exists")
        waiter.wait(TableName=table_name)


def run_migrations(reset: bool = False, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    prefix = settings.dynamodb_table_prefix
    if reset:
        delete_tables(prefix, settings)
    create_tables(prefix, settings)

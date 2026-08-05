from typing import Any, TypedDict


class GlobalSecondaryIndex(TypedDict):
    IndexName: str
    KeySchema: list[dict[str, str]]
    Projection: dict[str, str]


class TableDefinition(TypedDict):
    suffix: str
    key_schema: list[dict[str, str]]
    attribute_definitions: list[dict[str, str]]
    global_secondary_indexes: list[GlobalSecondaryIndex]


TABLE_DEFINITIONS: list[TableDefinition] = [
    {
        "suffix": "tickets",
        "key_schema": [{"AttributeName": "ticketId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "ticketId", "AttributeType": "S"},
            {"AttributeName": "ticketNumber", "AttributeType": "S"},
            {"AttributeName": "trackingCode", "AttributeType": "S"},
            {"AttributeName": "ownerUserId", "AttributeType": "S"},
            {"AttributeName": "ownerHistorySortKey", "AttributeType": "S"},
            {"AttributeName": "publicStatus", "AttributeType": "S"},
            {"AttributeName": "publicSortKey", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "ticketNumber-index",
                "KeySchema": [{"AttributeName": "ticketNumber", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "trackingCode-index",
                "KeySchema": [{"AttributeName": "trackingCode", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "ownerUserId-ownerHistorySortKey-index",
                "KeySchema": [
                    {"AttributeName": "ownerUserId", "KeyType": "HASH"},
                    {"AttributeName": "ownerHistorySortKey", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "publicStatus-publicSortKey-index",
                "KeySchema": [
                    {"AttributeName": "publicStatus", "KeyType": "HASH"},
                    {"AttributeName": "publicSortKey", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "users",
        "key_schema": [{"AttributeName": "userId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "userId", "AttributeType": "S"},
            {"AttributeName": "phone", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                # Read/reconciliation aid only — phone-claims is the uniqueness authority.
                "IndexName": "phone-index",
                "KeySchema": [{"AttributeName": "phone", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "phone-claims",
        "key_schema": [{"AttributeName": "phoneKey", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "phoneKey", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "citizen-otp-challenges",
        "key_schema": [{"AttributeName": "challengeId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "challengeId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "citizen-sessions",
        "key_schema": [{"AttributeName": "sessionId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "sessionId", "AttributeType": "S"},
            {"AttributeName": "userId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "userId-index",
                "KeySchema": [{"AttributeName": "userId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "staff-users",
        "key_schema": [{"AttributeName": "staffId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "staffId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "staff-username-claims",
        "key_schema": [{"AttributeName": "usernameKey", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "usernameKey", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "staff-password-reset-challenges",
        "key_schema": [{"AttributeName": "challengeId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "challengeId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "municipalities",
        "key_schema": [{"AttributeName": "municipalityId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "municipalityId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "departments",
        "key_schema": [{"AttributeName": "departmentId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "departmentId", "AttributeType": "S"},
            {"AttributeName": "municipalityId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "municipalityId-index",
                "KeySchema": [{"AttributeName": "municipalityId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "ticket-status-history",
        "key_schema": [{"AttributeName": "historyId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "historyId", "AttributeType": "S"},
            {"AttributeName": "ticketId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "ticketId-index",
                "KeySchema": [{"AttributeName": "ticketId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "ticket-audit-history",
        "key_schema": [{"AttributeName": "auditId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "auditId", "AttributeType": "S"},
            {"AttributeName": "ticketId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "ticketId-index",
                "KeySchema": [{"AttributeName": "ticketId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "ai-outputs",
        "key_schema": [{"AttributeName": "aiOutputId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "aiOutputId", "AttributeType": "S"},
            {"AttributeName": "ticketId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [
            {
                "IndexName": "ticketId-index",
                "KeySchema": [{"AttributeName": "ticketId", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    },
    {
        "suffix": "duplicate-groups",
        "key_schema": [{"AttributeName": "duplicateGroupId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "duplicateGroupId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "categories",
        "key_schema": [{"AttributeName": "categoryId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "categoryId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        "suffix": "counters",
        "key_schema": [{"AttributeName": "counterId", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "counterId", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
    {
        # Shared fixed-window rate-limit counters (issue #186). TTL on expiresAt.
        "suffix": "rate-limit-buckets",
        "key_schema": [{"AttributeName": "bucketKey", "KeyType": "HASH"}],
        "attribute_definitions": [
            {"AttributeName": "bucketKey", "AttributeType": "S"},
        ],
        "global_secondary_indexes": [],
    },
]


def build_table_name(prefix: str, suffix: str) -> str:
    return f"{prefix}{suffix}"


def build_create_table_params(prefix: str, definition: TableDefinition) -> dict[str, Any]:
    table_name = build_table_name(prefix, definition["suffix"])
    params: dict[str, Any] = {
        "TableName": table_name,
        "KeySchema": definition["key_schema"],
        "AttributeDefinitions": definition["attribute_definitions"],
        "BillingMode": "PAY_PER_REQUEST",
    }
    if definition["global_secondary_indexes"]:
        params["GlobalSecondaryIndexes"] = definition["global_secondary_indexes"]
    return params

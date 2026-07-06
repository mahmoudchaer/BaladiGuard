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

    for table_name in created_tables:
        wait_for_table(client, table_name)

    return created_tables


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

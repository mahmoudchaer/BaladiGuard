import os

os.environ["DATABASE_BACKEND"] = "memory"

import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.config import Settings, get_settings
from app.database.memory import ticket_store
from app.database.memory_status_history import status_history_store
from app.database.migrations import create_tables
from app.main import app


@pytest.fixture(autouse=True)
def reset_ticket_store() -> None:
    ticket_store.clear()
    status_history_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def dynamodb_settings() -> Settings:
    original_backend = os.environ.get("DATABASE_BACKEND")
    original_region = os.environ.get("AWS_REGION")
    original_endpoint = os.environ.get("DYNAMODB_ENDPOINT_URL")
    original_seed = os.environ.get("SEED_SAMPLE_TICKETS")

    with mock_aws():
        os.environ["DATABASE_BACKEND"] = "dynamodb"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["SEED_SAMPLE_TICKETS"] = "false"
        os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
        get_settings.cache_clear()

        settings = Settings()
        create_tables(settings.dynamodb_table_prefix, settings)

        yield settings

    if original_backend is None:
        os.environ.pop("DATABASE_BACKEND", None)
    else:
        os.environ["DATABASE_BACKEND"] = original_backend

    if original_region is None:
        os.environ.pop("AWS_REGION", None)
    else:
        os.environ["AWS_REGION"] = original_region

    if original_endpoint is None:
        os.environ.pop("DYNAMODB_ENDPOINT_URL", None)
    else:
        os.environ["DYNAMODB_ENDPOINT_URL"] = original_endpoint

    if original_seed is None:
        os.environ.pop("SEED_SAMPLE_TICKETS", None)
    else:
        os.environ["SEED_SAMPLE_TICKETS"] = original_seed

    get_settings.cache_clear()

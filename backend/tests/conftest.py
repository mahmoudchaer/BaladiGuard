import os

os.environ["DATABASE_BACKEND"] = "memory"

import pytest
from fastapi.testclient import TestClient

from app.database.memory import ticket_store
from app.main import app


@pytest.fixture(autouse=True)
def reset_ticket_store() -> None:
    ticket_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

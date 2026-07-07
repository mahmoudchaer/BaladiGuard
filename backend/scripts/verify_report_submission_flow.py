"""Verify the real upload-then-submit report flow against configured services."""

from __future__ import annotations

import os
import subprocess
import sys

SCRIPT = """
import os
from fastapi.testclient import TestClient
from app.database.memory import ticket_store
from app.main import app

client = TestClient(app)
upload = client.post(
    "/v1/uploads/report-photo",
    files={"file": ("flow-check.jpg", b"baladiguard-flow-check", "image/jpeg")},
    headers={"X-Client-Version": "mobile-0.1.0"},
)
if upload.status_code != 200:
    print("upload_status", upload.status_code)
    print("upload_body", upload.json())
    raise SystemExit(1)

image_object_key = upload.json()["imageObjectKey"]
submit = client.post(
    "/v1/tickets",
    json={
        "description": "Large pothole near the university gate causing traffic disruption.",
        "languageHint": "auto",
        "contact": {
            "name": "Citizen Name",
            "phone": "+96170123456",
            "email": "citizen@example.com",
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
    raise SystemExit(1)

body = submit.json()
stored = ticket_store.get(body["ticketId"])
if stored is None or stored.image_object_key != image_object_key:
    raise SystemExit(1)

print("upload_key", image_object_key)
print("ticket_number", body["ticketNumber"])
print("tracking_code", body["trackingCode"])
"""


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["DATABASE_BACKEND"] = "memory"

    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return 1

    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

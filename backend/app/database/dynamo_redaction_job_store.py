from __future__ import annotations

from uuid import uuid4

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.memory_redaction_job import redaction_job_id
from app.schemas.stored_redaction_job import StoredRedactionJob


class DynamoRedactionJobStore:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._table = create_dynamodb_resource(settings).Table(
            build_table_name(settings.dynamodb_table_prefix, "image-redaction-jobs")
        )

    def enqueue(self, ticket_id: str, generation: int, now: int) -> StoredRedactionJob:
        job = StoredRedactionJob(
            jobId=redaction_job_id(ticket_id, generation),
            ticketId=ticket_id,
            generation=generation,
            status="queued",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
        try:
            self._table.put_item(
                Item=job.model_dump(by_alias=True, exclude_none=True),
                ConditionExpression="attribute_not_exists(jobId)",
            )
            return job
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            existing = self.get(job.job_id)
            if existing is None:
                raise
            return existing

    def get(self, job_id: str) -> StoredRedactionJob | None:
        item = self._table.get_item(Key={"jobId": job_id}, ConsistentRead=True).get("Item")
        return StoredRedactionJob.model_validate(item) if item else None

    def claim_next(self, *, now: int, claim_ttl_seconds: int) -> StoredRedactionJob | None:
        candidates = sorted(
            self._scan(Attr("status").eq("queued") & Attr("availableAt").lte(now)),
            key=lambda i: (int(i["availableAt"]), int(i["createdAt"]), i["jobId"]),
        )
        for item in candidates:
            token = uuid4().hex
            try:
                response = self._table.update_item(
                    Key={"jobId": item["jobId"]},
                    UpdateExpression=(
                        "SET #s=:running, attempts=attempts+:one, claimToken=:token, "
                        "claimExpiresAt=:expires, updatedAt=:now"
                    ),
                    ConditionExpression="#s=:queued AND availableAt<=:now",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":running": "running",
                        ":queued": "queued",
                        ":one": 1,
                        ":token": token,
                        ":expires": now + claim_ttl_seconds,
                        ":now": now,
                    },
                    ReturnValues="ALL_NEW",
                )
                return StoredRedactionJob.model_validate(response["Attributes"])
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
        return None

    def succeed(self, job_id: str, claim_token: str, now: int) -> bool:
        return self._transition(
            job_id,
            claim_token,
            "SET #s=:target, updatedAt=:now REMOVE claimToken, claimExpiresAt, lastErrorCode",
            {":target": "succeeded", ":now": now},
        )

    def retry(
        self, job_id: str, claim_token: str, *, available_at: int, now: int, reason: str
    ) -> bool:
        return self._transition(
            job_id,
            claim_token,
            (
                "SET #s=:target, availableAt=:available, updatedAt=:now, "
                "lastErrorCode=:reason REMOVE claimToken, claimExpiresAt"
            ),
            {":target": "queued", ":available": available_at, ":now": now, ":reason": reason},
        )

    def dead_letter(self, job_id: str, claim_token: str, *, now: int, reason: str) -> bool:
        return self._transition(
            job_id,
            claim_token,
            (
                "SET #s=:target, updatedAt=:now, lastErrorCode=:reason "
                "REMOVE claimToken, claimExpiresAt"
            ),
            {":target": "dead_lettered", ":now": now, ":reason": reason},
        )

    def recover_stale(self, *, now: int) -> list[StoredRedactionJob]:
        recovered = []
        for item in self._scan(Attr("status").eq("running") & Attr("claimExpiresAt").lte(now)):
            token = item.get("claimToken")
            if token and self.retry(
                item["jobId"], token, available_at=now, now=now, reason="CLAIM_EXPIRED"
            ):
                # Preserve the expired token for the ticket store's ownership
                # condition; the persisted job itself is already queued.
                recovered.append(StoredRedactionJob.model_validate(item))
        return recovered

    def replay(self, job_id: str, *, now: int) -> StoredRedactionJob | None:
        try:
            response = self._table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=(
                    "SET #status = :queued, attempts = :zero, availableAt = :now, "
                    "updatedAt = :now REMOVE claimToken, claimExpiresAt, lastErrorCode"
                ),
                ConditionExpression="#status = :dead",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":queued": "queued",
                    ":dead": "dead_lettered",
                    ":zero": 0,
                    ":now": now,
                },
                ReturnValues="ALL_NEW",
            )
            return StoredRedactionJob.model_validate(response["Attributes"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def list(self) -> list[StoredRedactionJob]:
        return [StoredRedactionJob.model_validate(i) for i in self._scan()]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed redaction jobs.")

    def _scan(self, expression=None) -> list[dict]:
        items = []
        start = None
        while True:
            kwargs = {}
            if expression is not None:
                kwargs["FilterExpression"] = expression
            if start:
                kwargs["ExclusiveStartKey"] = start
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            start = response.get("LastEvaluatedKey")
            if not start:
                return items

    def _transition(self, job_id: str, token: str, update: str, values: dict) -> bool:
        try:
            self._table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update,
                ConditionExpression="#s=:running AND claimToken=:token",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={**values, ":running": "running", ":token": token},
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

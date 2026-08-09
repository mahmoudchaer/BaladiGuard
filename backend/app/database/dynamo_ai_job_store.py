from __future__ import annotations

from uuid import uuid4

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name
from app.database.memory_ai_job import ai_job_id
from app.schemas.stored_ai_job import StoredAiJob


def _job(item: dict) -> StoredAiJob:
    return StoredAiJob.model_validate(item)


class DynamoAiJobStore:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        resource = create_dynamodb_resource(settings)
        self._table = resource.Table(
            build_table_name(settings.dynamodb_table_prefix, "ai-processing-jobs")
        )

    def enqueue(self, ticket_id: str, now: int) -> StoredAiJob:
        job = StoredAiJob(
            jobId=ai_job_id(ticket_id),
            ticketId=ticket_id,
            status="queued",
            availableAt=now,
            createdAt=now,
            updatedAt=now,
        )
        item = job.model_dump(by_alias=True, exclude_none=True)
        try:
            self._table.put_item(
                Item=item,
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

    def get(self, job_id: str) -> StoredAiJob | None:
        item = self._table.get_item(Key={"jobId": job_id}, ConsistentRead=True).get("Item")
        return _job(item) if item else None

    def claim_next(self, *, now: int, claim_ttl_seconds: int) -> StoredAiJob | None:
        candidates = self._scan_all(
            filter_expression=Attr("status").eq("queued") & Attr("availableAt").lte(now)
        )
        candidates = sorted(
            candidates,
            key=lambda item: (int(item["availableAt"]), int(item["createdAt"]), item["jobId"]),
        )
        for candidate in candidates:
            token = uuid4().hex
            try:
                response = self._table.update_item(
                    Key={"jobId": candidate["jobId"]},
                    UpdateExpression=(
                        "SET #status = :running, attempts = attempts + :one, "
                        "claimToken = :token, claimExpiresAt = :expires, updatedAt = :now"
                    ),
                    ConditionExpression="#status = :queued AND availableAt <= :now",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":queued": "queued",
                        ":running": "running",
                        ":one": 1,
                        ":token": token,
                        ":expires": now + claim_ttl_seconds,
                        ":now": now,
                    },
                    ReturnValues="ALL_NEW",
                )
                return _job(response["Attributes"])
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
        return None

    def succeed(self, job_id: str, claim_token: str, now: int) -> bool:
        return self._finish(job_id, claim_token, now=now, status="succeeded", reason=None)

    def retry(
        self,
        job_id: str,
        claim_token: str,
        *,
        available_at: int,
        now: int,
        reason: str,
    ) -> bool:
        return self._transition_claimed(
            job_id,
            claim_token,
            update=(
                "SET #status = :queued, availableAt = :available, updatedAt = :now, "
                "lastError = :reason REMOVE claimToken, claimExpiresAt"
            ),
            values={
                ":queued": "queued",
                ":available": available_at,
                ":now": now,
                ":reason": reason,
            },
        )

    def dead_letter(self, job_id: str, claim_token: str, *, now: int, reason: str) -> bool:
        return self._finish(job_id, claim_token, now=now, status="dead_lettered", reason=reason)

    def recover_stale(self, *, now: int) -> list[StoredAiJob]:
        items = self._scan_all(
            filter_expression=Attr("status").eq("running") & Attr("claimExpiresAt").lte(now)
        )
        recovered: list[StoredAiJob] = []
        for item in items:
            try:
                response = self._table.update_item(
                    Key={"jobId": item["jobId"]},
                    UpdateExpression=(
                        "SET #status = :queued, availableAt = :now, updatedAt = :now, "
                        "lastError = :reason REMOVE claimToken, claimExpiresAt"
                    ),
                    ConditionExpression=("#status = :running AND claimExpiresAt <= :now"),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":queued": "queued",
                        ":running": "running",
                        ":now": now,
                        ":reason": "Worker claim expired before completion.",
                    },
                    ReturnValues="ALL_NEW",
                )
                recovered.append(_job(response["Attributes"]))
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
        return recovered

    def replay(self, job_id: str, *, now: int) -> StoredAiJob | None:
        try:
            response = self._table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=(
                    "SET #status = :queued, attempts = :zero, availableAt = :now, "
                    "updatedAt = :now REMOVE claimToken, claimExpiresAt, lastError"
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
            return _job(response["Attributes"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise

    def list(self) -> list[StoredAiJob]:
        return [_job(item) for item in self._scan_all()]

    def clear(self) -> None:
        raise NotImplementedError("Use db-reset for DynamoDB-backed AI jobs.")

    def _scan_all(self, *, filter_expression=None) -> list[dict]:
        items: list[dict] = []
        start_key = None
        while True:
            kwargs = {}
            if filter_expression is not None:
                kwargs["FilterExpression"] = filter_expression
            if start_key is not None:
                kwargs["ExclusiveStartKey"] = start_key
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            start_key = response.get("LastEvaluatedKey")
            if not start_key:
                return items

    def _finish(
        self,
        job_id: str,
        claim_token: str,
        *,
        now: int,
        status: str,
        reason: str | None,
    ) -> bool:
        update = (
            "SET #status = :target, updatedAt = :now"
            + (", lastError = :reason" if reason else "")
            + " REMOVE claimToken, claimExpiresAt"
            + ("" if reason else ", lastError")
        )
        values = {":target": status, ":now": now}
        if reason:
            values[":reason"] = reason
        return self._transition_claimed(job_id, claim_token, update=update, values=values)

    def _transition_claimed(
        self,
        job_id: str,
        claim_token: str,
        *,
        update: str,
        values: dict,
    ) -> bool:
        values = {**values, ":running": "running", ":token": claim_token}
        try:
            self._table.update_item(
                Key={"jobId": job_id},
                UpdateExpression=update,
                ConditionExpression="#status = :running AND claimToken = :token",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=values,
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

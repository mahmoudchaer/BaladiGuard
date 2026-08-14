"""DynamoDB-backed fixed-window rate limiter shared across instances (issue #186)."""

from __future__ import annotations

import time
from decimal import Decimal

from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.core.rate_limit import RateLimitDecision, RateLimitPolicy
from app.database.dynamodb import create_dynamodb_resource
from app.database.dynamodb_tables import build_table_name


class DynamoRateLimiter:
    """Aligned fixed-window counters stored in DynamoDB for multi-instance safety."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._resource = create_dynamodb_resource(self._settings)
        prefix = self._settings.dynamodb_table_prefix
        self._table = self._resource.Table(build_table_name(prefix, "rate-limit-buckets"))

    def check(
        self,
        *,
        policy: RateLimitPolicy,
        client_key: str,
        now: float | None = None,
    ) -> RateLimitDecision:
        current_time = time.time() if now is None else now
        window_start = int(current_time // policy.window_seconds) * policy.window_seconds
        reset_at = window_start + policy.window_seconds
        bucket_key = f"{policy.name}:{window_start}:{client_key}"
        expires_at = int(reset_at) + 60  # TTL grace past window end

        try:
            response = self._table.update_item(
                Key={"bucketKey": bucket_key},
                UpdateExpression=(
                    "SET #count = if_not_exists(#count, :zero) + :one, "
                    "expiresAt = if_not_exists(expiresAt, :expires_at), "
                    "policyName = if_not_exists(policyName, :policy)"
                ),
                ExpressionAttributeNames={"#count": "count"},
                ExpressionAttributeValues={
                    ":zero": Decimal(0),
                    ":one": Decimal(1),
                    ":expires_at": Decimal(expires_at),
                    ":policy": policy.name,
                },
                ReturnValues="UPDATED_NEW",
            )
        except ClientError:
            # Fail closed on storage errors so abuse cannot bypass limits.
            from app.core.metrics import emit_metric

            emit_metric(
                "DynamoDbErrors",
                dimensions={"operation": "rate_limit_check"},
            )
            retry_after = max(1, policy.window_seconds)
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

        count = int(response["Attributes"]["count"])
        if count > policy.limit:
            retry_after = max(1, int(reset_at - current_time))
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
        return RateLimitDecision(allowed=True, retry_after_seconds=0)

    def reset(self) -> None:
        """Best-effort clear for tests (scan + delete). Not used in production."""
        scan_kwargs: dict = {}
        while True:
            response = self._table.scan(**scan_kwargs)
            with self._table.batch_writer() as batch:
                for item in response.get("Items", []):
                    batch.delete_item(Key={"bucketKey": item["bucketKey"]})
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            scan_kwargs["ExclusiveStartKey"] = last_key

import hashlib
import os
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.database.photo_claim_store import PhotoClaimStore

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
FORMAT_DETAILS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
OWNER_SCOPE_LENGTH = 24
KEY_PREFIX = "reports/photos/v2"
EVIDENCE_KEY_PREFIX = "work-orders/evidence/v1"


class InvalidUploadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class S3UploadError(RuntimeError):
    pass


@dataclass(frozen=True)
class SanitizedImage:
    body: bytes
    extension: str
    content_type: str


class PhotoUploadService:
    def __init__(self) -> None:
        self._s3_client = None

    def _get_s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                region_name=os.environ.get("AWS_REGION", "us-east-1").strip() or "us-east-1",
            )
        return self._s3_client

    @staticmethod
    def _get_bucket_name() -> str:
        bucket = os.environ.get("AWS_S3_BUCKET", "").strip()
        if not bucket:
            raise S3UploadError("S3 upload storage is not configured.")
        return bucket

    async def upload_report_photo(self, file: UploadFile, *, owner_user_id: str) -> str:
        claimed_extension = self._get_extension(file.filename)
        self._validate_content_type(file.content_type)
        contents = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidUploadError(
                code="FILE_TOO_LARGE",
                message="Image file must be 5MB or smaller.",
            )

        image = self._sanitize_image(contents)
        if claimed_extension == "jpeg":
            claimed_extension = "jpg"
        if claimed_extension != image.extension or file.content_type != image.content_type:
            raise InvalidUploadError(
                code="IMAGE_TYPE_MISMATCH",
                message="The image contents do not match the declared file type.",
            )

        return self._store_sanitized_report_photo(image, owner_user_id=owner_user_id)

    def upload_report_photo_bytes(
        self,
        contents: bytes,
        *,
        owner_user_id: str,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        """Sanitize provider image bytes and store under the owner-scoped orphan contract."""
        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidUploadError(
                code="FILE_TOO_LARGE",
                message="Image file must be 5MB or smaller.",
            )
        if content_type:
            self._validate_content_type(content_type)
        image = self._sanitize_image(contents)
        if content_type and content_type != image.content_type:
            raise InvalidUploadError(
                code="IMAGE_TYPE_MISMATCH",
                message="The image contents do not match the declared file type.",
            )
        if filename:
            claimed_extension = self._get_extension(filename)
            if claimed_extension == "jpeg":
                claimed_extension = "jpg"
            if claimed_extension != image.extension:
                raise InvalidUploadError(
                    code="IMAGE_TYPE_MISMATCH",
                    message="The image contents do not match the declared file type.",
                )
        return self._store_sanitized_report_photo(image, owner_user_id=owner_user_id)

    def _store_sanitized_report_photo(self, image: SanitizedImage, *, owner_user_id: str) -> str:
        owner_scope = self.owner_scope(owner_user_id)
        storage_key = f"{KEY_PREFIX}/{owner_scope}/{uuid4().hex}.{image.extension}"
        tags = urlencode(
            {"upload-state": "orphan", "owner-scope": owner_scope},
            safe="",
        )
        try:
            self._get_s3_client().put_object(
                Bucket=self._get_bucket_name(),
                Key=storage_key,
                Body=image.body,
                ContentType=image.content_type,
                ServerSideEncryption="AES256",
                Tagging=tags,
                Metadata={"sanitized": "true"},
            )
        except (BotoCoreError, ClientError) as exc:
            from app.core.metrics import emit_metric

            emit_metric("S3Errors", dimensions={"operation": "put_report_photo"})
            raise S3UploadError("Failed to upload image to storage.") from exc
        return storage_key

    async def upload_work_order_evidence(
        self,
        file: UploadFile,
        *,
        ticket_id: str,
        work_order_id: str,
        kind: str,
    ) -> tuple[str, str]:
        """Sanitize and store a staff before/after image under a ticket-bound key."""
        claimed_extension = self._get_extension(file.filename)
        self._validate_content_type(file.content_type)
        contents = await file.read(MAX_IMAGE_SIZE_BYTES + 1)
        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidUploadError(
                code="FILE_TOO_LARGE",
                message="Image file must be 5MB or smaller.",
            )

        image = self._sanitize_image(contents)
        if claimed_extension == "jpeg":
            claimed_extension = "jpg"
        if claimed_extension != image.extension or file.content_type != image.content_type:
            raise InvalidUploadError(
                code="IMAGE_TYPE_MISMATCH",
                message="The image contents do not match the declared file type.",
            )

        ticket_scope = self.ticket_scope(ticket_id)
        kind_scope = kind.strip().lower()
        storage_key = (
            f"{EVIDENCE_KEY_PREFIX}/{ticket_scope}/{work_order_id}/{kind_scope}/"
            f"{uuid4().hex}.{image.extension}"
        )
        tags = urlencode(
            {
                "upload-state": "linked",
                "ticket-scope": ticket_scope,
                "work-order-id": work_order_id,
                "evidence-kind": kind_scope,
            },
            safe="",
        )
        try:
            self._get_s3_client().put_object(
                Bucket=self._get_bucket_name(),
                Key=storage_key,
                Body=image.body,
                ContentType=image.content_type,
                ServerSideEncryption="AES256",
                Tagging=tags,
                Metadata={"sanitized": "true"},
            )
        except (BotoCoreError, ClientError) as exc:
            from app.core.metrics import emit_metric

            emit_metric("S3Errors", dimensions={"operation": "put_work_order_evidence"})
            raise S3UploadError("Failed to upload image to storage.") from exc
        return storage_key, image.content_type

    @staticmethod
    def _get_claim_store() -> PhotoClaimStore:
        if get_settings().use_dynamodb:
            from app.database.dynamo_photo_claim_store import DynamoPhotoClaimStore

            return DynamoPhotoClaimStore()
        from app.database.memory_photo_claim import photo_claim_store

        return photo_claim_store

    def claim_for_ticket(self, object_key: str, *, owner_user_id: str, ticket_id: str) -> bool:
        """Bind a new v2 upload to its owner/ticket; legacy fixture keys are untouched."""
        if not object_key.startswith(f"{KEY_PREFIX}/"):
            return False
        owner_scope = self.owner_scope(owner_user_id)
        if not object_key.startswith(f"{KEY_PREFIX}/{owner_scope}/"):
            raise InvalidUploadError(
                code="PHOTO_NOT_OWNED",
                message="The selected photo does not belong to this account.",
            )
        claim_store = self._get_claim_store()
        claim_acquired = False
        try:
            tags = (
                self._get_s3_client()
                .get_object_tagging(Bucket=self._get_bucket_name(), Key=object_key)
                .get("TagSet", [])
            )
            tag_map = {item["Key"]: item["Value"] for item in tags}
            if tag_map.get("owner-scope") != owner_scope:
                raise InvalidUploadError(
                    code="PHOTO_NOT_OWNED",
                    message="The selected photo does not belong to this account.",
                )
            if tag_map.get("upload-state") == "linked":
                raise InvalidUploadError(
                    code="PHOTO_ALREADY_USED",
                    message="The selected photo is already attached to a report.",
                )
            claim_acquired = claim_store.claim(
                object_key,
                owner_scope=owner_scope,
                ticket_id=ticket_id,
            )
            if not claim_acquired:
                raise InvalidUploadError(
                    code="PHOTO_ALREADY_USED",
                    message="The selected photo is already attached to a report.",
                )
            self._get_s3_client().put_object_tagging(
                Bucket=self._get_bucket_name(),
                Key=object_key,
                Tagging={
                    "TagSet": [
                        {"Key": "upload-state", "Value": "linked"},
                        {"Key": "owner-scope", "Value": owner_scope},
                        {
                            "Key": "ticket-scope",
                            "Value": self.ticket_scope(ticket_id),
                        },
                    ]
                },
            )
            return True
        except InvalidUploadError:
            raise
        except (BotoCoreError, ClientError) as exc:
            if claim_acquired:
                claim_store.release(object_key, ticket_id=ticket_id)
            raise S3UploadError("Could not verify photo ownership.") from exc

    def rollback_ticket_claim(
        self,
        object_key: str,
        *,
        owner_user_id: str,
        ticket_id: str,
    ) -> None:
        """Restore the orphan state after ticket persistence fails."""
        if not object_key.startswith(f"{KEY_PREFIX}/"):
            return
        owner_scope = self.owner_scope(owner_user_id)
        try:
            self._get_s3_client().put_object_tagging(
                Bucket=self._get_bucket_name(),
                Key=object_key,
                Tagging={
                    "TagSet": [
                        {"Key": "upload-state", "Value": "orphan"},
                        {"Key": "owner-scope", "Value": owner_scope},
                    ]
                },
            )
            if not self._get_claim_store().release(object_key, ticket_id=ticket_id):
                raise S3UploadError("Could not release photo claim after ticket save failure.")
        except (BotoCoreError, ClientError) as exc:
            raise S3UploadError("Could not release photo claim after ticket save failure.") from exc

    @staticmethod
    def owner_scope(owner_user_id: str) -> str:
        return hashlib.sha256(owner_user_id.encode()).hexdigest()[:OWNER_SCOPE_LENGTH]

    @staticmethod
    def ticket_scope(ticket_id: str) -> str:
        return hashlib.sha256(ticket_id.encode()).hexdigest()[:OWNER_SCOPE_LENGTH]

    @staticmethod
    def _sanitize_image(contents: bytes) -> SanitizedImage:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(contents)) as opened:
                    opened.verify()
                with Image.open(BytesIO(contents)) as opened:
                    width, height = opened.size
                    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                        raise InvalidUploadError(
                            code="IMAGE_DIMENSIONS_TOO_LARGE",
                            message="Image dimensions are too large.",
                        )
                    if getattr(opened, "is_animated", False) or getattr(opened, "n_frames", 1) > 1:
                        raise InvalidUploadError(
                            code="UNSUPPORTED_IMAGE",
                            message="Animated images are not supported.",
                        )
                    details = FORMAT_DETAILS.get(opened.format or "")
                    if details is None:
                        raise InvalidUploadError(
                            code="UNSUPPORTED_IMAGE",
                            message="Only JPEG, PNG, and WebP images are supported.",
                        )
                    extension, content_type = details
                    sanitized = ImageOps.exif_transpose(opened)
                    sanitized.load()
                    if extension in {"jpg", "webp"} and sanitized.mode not in {"RGB", "L"}:
                        background = Image.new("RGB", sanitized.size, "white")
                        if "A" in sanitized.getbands():
                            background.paste(sanitized, mask=sanitized.getchannel("A"))
                        else:
                            background.paste(sanitized.convert("RGB"))
                        sanitized = background
                    output = BytesIO()
                    save_options = {"optimize": True}
                    if extension in {"jpg", "webp"}:
                        save_options["quality"] = 85
                    sanitized.save(output, format=opened.format, **save_options)
                    return SanitizedImage(output.getvalue(), extension, content_type)
        except InvalidUploadError:
            raise
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise InvalidUploadError(
                code="INVALID_IMAGE_CONTENT",
                message="The uploaded file is not a valid image.",
            ) from exc
        except Image.DecompressionBombWarning as exc:
            raise InvalidUploadError(
                code="IMAGE_DIMENSIONS_TOO_LARGE",
                message="Image dimensions are too large.",
            ) from exc

    @staticmethod
    def _get_extension(filename: str | None) -> str:
        extension = Path(filename or "").suffix.removeprefix(".").lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise InvalidUploadError(
                code="INVALID_FILE_TYPE",
                message="Image file must be a jpg, jpeg, png, or webp file.",
            )
        return extension

    @staticmethod
    def _validate_content_type(content_type: str | None) -> None:
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise InvalidUploadError(
                code="INVALID_FILE_TYPE",
                message="Image file content type must be image/jpeg, image/png, or image/webp.",
            )


photo_upload_service = PhotoUploadService()

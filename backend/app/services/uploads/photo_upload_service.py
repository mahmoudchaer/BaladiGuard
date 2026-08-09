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

    def claim_for_ticket(self, object_key: str, *, owner_user_id: str, ticket_id: str) -> None:
        """Bind a new v2 upload to its owner/ticket; legacy fixture keys are untouched."""
        if not object_key.startswith(f"{KEY_PREFIX}/"):
            return
        owner_scope = self.owner_scope(owner_user_id)
        if not object_key.startswith(f"{KEY_PREFIX}/{owner_scope}/"):
            raise InvalidUploadError(
                code="PHOTO_NOT_OWNED",
                message="The selected photo does not belong to this account.",
            )
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
            self._get_s3_client().put_object_tagging(
                Bucket=self._get_bucket_name(),
                Key=object_key,
                Tagging={
                    "TagSet": [
                        {"Key": "upload-state", "Value": "linked"},
                        {"Key": "owner-scope", "Value": owner_scope},
                        {
                            "Key": "ticket-scope",
                            "Value": hashlib.sha256(ticket_id.encode()).hexdigest()[:24],
                        },
                    ]
                },
            )
        except InvalidUploadError:
            raise
        except (BotoCoreError, ClientError) as exc:
            raise S3UploadError("Could not verify photo ownership.") from exc

    @staticmethod
    def owner_scope(owner_user_id: str) -> str:
        return hashlib.sha256(owner_user_id.encode()).hexdigest()[:OWNER_SCOPE_LENGTH]

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

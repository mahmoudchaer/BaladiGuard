import os
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
REQUIRED_AWS_ENV_VARS = (
    "AWS_REGION",
    "AWS_S3_BUCKET",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)


class InvalidUploadError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class S3UploadError(RuntimeError):
    pass


class PhotoUploadService:
    def __init__(self) -> None:
        self._s3_client = None

    def _get_s3_client(self):
        if self._s3_client is None:
            config = self._get_aws_config()
            self._s3_client = boto3.client(
                "s3",
                region_name=config["AWS_REGION"],
                aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
            )
        return self._s3_client

    def _get_bucket_name(self) -> str:
        return self._get_aws_config()["AWS_S3_BUCKET"]

    @staticmethod
    def _get_aws_config() -> dict[str, str]:
        config = {name: os.environ.get(name, "") for name in REQUIRED_AWS_ENV_VARS}
        if any(not value for value in config.values()):
            raise S3UploadError("S3 upload storage is not configured.")
        return config

    async def upload_report_photo(self, file: UploadFile) -> str:
        extension = self._get_extension(file.filename)
        self._validate_content_type(file.content_type)
        contents = await file.read()

        if len(contents) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidUploadError(
                code="FILE_TOO_LARGE",
                message="Image file must be 5MB or smaller.",
            )

        storage_key = f"reports/photos/{uuid4()}.{extension}"

        try:
            self._get_s3_client().put_object(
                Bucket=self._get_bucket_name(),
                Key=storage_key,
                Body=contents,
                ContentType=file.content_type or f"image/{extension}",
            )
        except (BotoCoreError, ClientError) as exc:
            raise S3UploadError("Failed to upload image to storage.") from exc

        return storage_key

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

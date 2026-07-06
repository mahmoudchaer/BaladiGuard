import boto3
from boto3.resources.base import ServiceResource
from botocore.client import BaseClient

from app.config import Settings, get_settings


def create_dynamodb_resource(settings: Settings | None = None) -> ServiceResource:
    settings = settings or get_settings()
    resource_kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        resource_kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return boto3.resource("dynamodb", **resource_kwargs)


def create_dynamodb_client(settings: Settings | None = None) -> BaseClient:
    settings = settings or get_settings()
    client_kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.dynamodb_endpoint_url:
        client_kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
    return boto3.client("dynamodb", **client_kwargs)

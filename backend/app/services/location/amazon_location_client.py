"""Amazon Location Service client for geocoding and reverse geocoding."""

from __future__ import annotations

import os
from typing import Any, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

import app.config  # noqa: F401 - ensure .env is loaded
from app.services.location.local_place_index import (
    is_within_beirut_bounds,
    search_local_places_by_position,
    search_local_places_by_text,
)


class LocationProviderError(RuntimeError):
    """Raised when the location provider cannot produce a usable result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LocationProvider(Protocol):
    def geocode_address(self, address_text: str) -> dict[str, Any]: ...

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]: ...


class AmazonLocationClient:
    def __init__(
        self,
        *,
        index_name: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.index_name = (
            index_name or os.environ.get("LOCATION_PLACE_INDEX_NAME", "").strip() or None
        )
        self.region_name = (
            region_name or os.environ.get("AWS_REGION", "us-east-1").strip() or "us-east-1"
        )
        self._client = client

    def _get_client(self):
        if self._client is None:
            kwargs: dict[str, Any] = {"region_name": self.region_name}
            access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
            secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key
            self._client = boto3.client("location", **kwargs)
        return self._client

    def geocode_address(self, address_text: str) -> dict[str, Any]:
        if not self.index_name:
            raise LocationProviderError(
                "LOCATION_PROVIDER_UNAVAILABLE",
                "Amazon Location place index is not configured.",
            )

        try:
            response = self._get_client().search_place_index_for_text(
                IndexName=self.index_name,
                Text=address_text,
                FilterCountries=["LBN"],
                MaxResults=1,
            )
        except (BotoCoreError, ClientError) as exc:
            raise LocationProviderError(
                "LOCATION_PROVIDER_UNAVAILABLE",
                "Location provider request failed.",
            ) from exc

        return self._parse_result(response, fallback_label=address_text)

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        if not self.index_name:
            raise LocationProviderError(
                "LOCATION_PROVIDER_UNAVAILABLE",
                "Amazon Location place index is not configured.",
            )

        try:
            response = self._get_client().search_place_index_for_position(
                IndexName=self.index_name,
                Position=[longitude, latitude],
                MaxResults=1,
            )
        except (BotoCoreError, ClientError) as exc:
            raise LocationProviderError(
                "LOCATION_PROVIDER_UNAVAILABLE",
                "Location provider request failed.",
            ) from exc

        return self._parse_result(
            response,
            fallback_label=f"{latitude:.5f}, {longitude:.5f}",
        )

    @staticmethod
    def _parse_result(response: dict[str, Any], *, fallback_label: str) -> dict[str, Any]:
        results = response.get("Results") or []
        if not results:
            raise LocationProviderError(
                "LOCATION_NOT_FOUND",
                "We could not find that location. Add more detail or choose a map point.",
            )

        place = results[0].get("Place") or {}
        geometry = place.get("Geometry") or {}
        position = geometry.get("Point") or []
        if len(position) < 2:
            raise LocationProviderError(
                "LOCATION_PROVIDER_UNAVAILABLE",
                "Location provider returned an incomplete result.",
            )

        longitude = float(position[0])
        latitude = float(position[1])
        label = str(place.get("Label") or fallback_label).strip() or fallback_label
        return {
            "latitude": latitude,
            "longitude": longitude,
            "addressText": label,
        }


class LocalLocationClient:
    """Deterministic local geocoder for CI and environments without Amazon Location."""

    def geocode_address(self, address_text: str) -> dict[str, Any]:
        place = search_local_places_by_text(address_text)
        if place is None:
            raise LocationProviderError(
                "LOCATION_NOT_FOUND",
                "We could not find that address. Try a Beirut landmark or choose a map point.",
            )
        return {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "addressText": place.address_text,
        }

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        if not is_within_beirut_bounds(latitude, longitude):
            raise LocationProviderError(
                "LOCATION_OUT_OF_SERVICE_AREA",
                "That location is outside the current BaladiGuard service area (Beirut).",
            )

        place = search_local_places_by_position(latitude, longitude)
        if place is None:
            return {
                "latitude": latitude,
                "longitude": longitude,
                "addressText": f"Selected map location ({latitude:.5f}, {longitude:.5f})",
            }

        return {
            "latitude": latitude,
            "longitude": longitude,
            "addressText": place.address_text,
        }


def build_location_provider() -> LocationProvider:
    index_name = os.environ.get("LOCATION_PLACE_INDEX_NAME", "").strip()
    if index_name:
        return AmazonLocationClient(index_name=index_name)
    return LocalLocationClient()


location_provider = build_location_provider()

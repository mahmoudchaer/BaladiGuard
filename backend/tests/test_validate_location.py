"""Unit tests for location validation (mocked provider + local place index)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.location_validation import ValidateLocationRequest
from app.services.location.amazon_location_client import (
    AmazonLocationClient,
    LocalLocationClient,
    LocationProviderError,
)
from app.services.location.validate_location import validate_location


class FakeLocationProvider:
    def __init__(self, payload: dict[str, Any] | Exception) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def geocode_address(self, address_text: str) -> dict[str, Any]:
        self.calls.append({"mode": "address", "address_text": address_text})
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        self.calls.append({"mode": "coordinates", "latitude": latitude, "longitude": longitude})
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_validate_location_geocodes_address_successfully() -> None:
    fake = FakeLocationProvider(
        {
            "latitude": 33.896112,
            "longitude": 35.478419,
            "addressText": "Near AUB Main Gate, Hamra, Beirut",
        }
    )

    result = validate_location(
        ValidateLocationRequest(addressText="AUB Main Gate, Hamra"),
        provider=fake,
    )

    assert result.success is True
    assert result.location is not None
    assert result.location.latitude == 33.896112
    assert result.location.source == "MANUAL"
    assert fake.calls[0]["mode"] == "address"


def test_validate_location_reverse_geocodes_coordinates_successfully() -> None:
    fake = FakeLocationProvider(
        {
            "latitude": 33.88694,
            "longitude": 35.48306,
            "addressText": "Verdun Street, Beirut",
        }
    )

    result = validate_location(
        ValidateLocationRequest(latitude=33.88694, longitude=35.48306),
        provider=fake,
    )

    assert result.success is True
    assert result.location is not None
    assert result.location.address_text == "Verdun Street, Beirut"
    assert result.location.source == "GPS"


def test_validate_location_returns_controlled_failure_for_not_found() -> None:
    fake = FakeLocationProvider(
        LocationProviderError("LOCATION_NOT_FOUND", "We could not find that location.")
    )

    result = validate_location(
        ValidateLocationRequest(addressText="unknown alley somewhere"),
        provider=fake,
    )

    assert result.success is False
    assert result.location is None
    assert result.message is not None
    assert "could not find" in result.message.lower()


def test_request_rejects_partial_coordinates() -> None:
    with pytest.raises(ValidationError):
        ValidateLocationRequest(latitude=33.89)


def test_request_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        ValidateLocationRequest()


def test_local_provider_geocodes_known_beirut_landmark() -> None:
    provider = LocalLocationClient()
    result = provider.geocode_address("AUB Main Gate")
    assert result["latitude"] == pytest.approx(33.896112)
    assert "Hamra" in result["addressText"]


def test_local_provider_rejects_unknown_address() -> None:
    provider = LocalLocationClient()
    with pytest.raises(LocationProviderError) as exc:
        provider.geocode_address("Somewhere on Mars crater 12")
    assert exc.value.code == "LOCATION_NOT_FOUND"


def test_local_provider_accepts_tripoli_coordinates() -> None:
    provider = LocalLocationClient()
    result = provider.reverse_geocode(34.4361, 35.8372)
    assert "Tripoli" in result["addressText"]


def test_local_provider_geocodes_tripoli_landmark() -> None:
    provider = LocalLocationClient()
    result = provider.geocode_address("Tripoli")
    assert result["latitude"] == pytest.approx(34.4361)
    assert "Tripoli" in result["addressText"]


def test_local_provider_rejects_coordinates_outside_service_area() -> None:
    provider = LocalLocationClient()
    with pytest.raises(LocationProviderError) as exc:
        provider.reverse_geocode(40.7128, -74.006)
    assert exc.value.code == "LOCATION_OUT_OF_SERVICE_AREA"


def test_amazon_client_parses_place_index_response() -> None:
    class StubBoto:
        def search_place_index_for_text(self, **kwargs: Any) -> dict[str, Any]:
            assert kwargs["FilterCountries"] == ["LBN"]
            return {
                "Results": [
                    {
                        "Place": {
                            "Label": "Near AUB Main Gate, Hamra, Beirut, Lebanon",
                            "Geometry": {"Point": [35.478419, 33.896112]},
                        }
                    }
                ]
            }

    client = AmazonLocationClient(index_name="baladiguard-places", client=StubBoto())
    result = client.geocode_address("AUB Main Gate")
    assert result["latitude"] == pytest.approx(33.896112)
    assert result["longitude"] == pytest.approx(35.478419)


def test_validate_location_endpoint_success(client) -> None:
    response = client.post(
        "/v1/locations/validate",
        json={"addressText": "Verdun Street, Beirut"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["location"]["latitude"] == pytest.approx(33.88694)
    assert body["location"]["longitude"] == pytest.approx(35.48306)
    assert body["location"]["source"] == "MANUAL"


def test_validate_location_endpoint_coordinates_success(client) -> None:
    response = client.post(
        "/v1/locations/validate",
        json={"latitude": 33.896112, "longitude": 35.478419},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["location"]["source"] == "GPS"
    assert "AUB" in body["location"]["addressText"] or "Hamra" in body["location"]["addressText"]


def test_validate_location_endpoint_rejects_unknown_address(client) -> None:
    response = client.post(
        "/v1/locations/validate",
        json={"addressText": "completely unknown desert outpost xyz"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "LOCATION_NOT_FOUND"


def test_validate_location_endpoint_rejects_out_of_area_coordinates(client) -> None:
    response = client.post(
        "/v1/locations/validate",
        json={"latitude": 48.8566, "longitude": 2.3522},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LOCATION_OUT_OF_SERVICE_AREA"


def test_validate_location_endpoint_rejects_invalid_payload(client) -> None:
    response = client.post("/v1/locations/validate", json={"latitude": 33.89})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

from __future__ import annotations

from scripts.backup.backup_controls import (
    DEFAULT_TABLE_SUFFIXES,
    _merged_s3_lifecycle,
    _s3_lifecycle,
)


def test_backup_scope_covers_persistent_mvp_data():
    assert {
        "tickets",
        "users",
        "phone-claims",
        "citizen-otp-challenges",
        "citizen-sessions",
        "staff-users",
        "staff-username-claims",
        "ticket-status-history",
        "ticket-audit-history",
        "duplicate-groups",
        "rate-limit-buckets",
    }.issubset(DEFAULT_TABLE_SUFFIXES)


def test_photo_lifecycle_retains_noncurrent_versions_and_aborts_multipart_uploads():
    rule = _s3_lifecycle()["Rules"][0]
    assert rule["Status"] == "Enabled"
    assert rule["Filter"]["Prefix"] == "reports/photos/"
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7


def test_photo_lifecycle_upsert_preserves_unrelated_rules():
    merged = _merged_s3_lifecycle(
        [
            {"ID": "KeepLogCleanup", "Status": "Enabled", "Filter": {"Prefix": "logs/"}},
            {"ID": "ReportPhotoVersionRetention", "Status": "Disabled"},
        ]
    )
    assert [rule["ID"] for rule in merged["Rules"]] == [
        "KeepLogCleanup",
        "ReportPhotoVersionRetention",
    ]
    assert merged["Rules"][1]["Status"] == "Enabled"


def test_photo_lifecycle_health_requires_expected_rule():
    rule = _s3_lifecycle()["Rules"][0]
    assert rule["ID"] == "ReportPhotoVersionRetention"
    assert rule["Filter"]["Prefix"] == "reports/photos/"
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90

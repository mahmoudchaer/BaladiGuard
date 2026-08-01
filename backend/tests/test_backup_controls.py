from __future__ import annotations

from scripts.backup.backup_controls import DEFAULT_TABLE_SUFFIXES, _s3_lifecycle


def test_backup_scope_covers_persistent_mvp_data():
    assert {
        "tickets",
        "users",
        "ticket-status-history",
        "ticket-audit-history",
        "duplicate-groups",
    }.issubset(DEFAULT_TABLE_SUFFIXES)


def test_photo_lifecycle_retains_noncurrent_versions_and_aborts_multipart_uploads():
    rule = _s3_lifecycle()["Rules"][0]
    assert rule["Status"] == "Enabled"
    assert rule["Filter"]["Prefix"] == "reports/photos/"
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7

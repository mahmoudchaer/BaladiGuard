from __future__ import annotations

from scripts.backup.backup_controls import (
    DEFAULT_TABLE_SUFFIXES,
    _merged_s3_lifecycle,
    _s3_lifecycle,
    apply,
)


def test_backup_scope_covers_persistent_mvp_data():
    assert {
        "tickets",
        "users",
        "phone-claims",
        "photo-upload-claims",
        "citizen-otp-challenges",
        "citizen-sessions",
        "staff-users",
        "staff-username-claims",
        "staff-password-reset-challenges",
        "ticket-status-history",
        "ticket-audit-history",
        "account-audit",
        "notification-deliveries",
        "notification-claims",
        "ticket-submission-claims",
        "ai-processing-jobs",
        "image-redaction-jobs",
        "duplicate-groups",
        "workforce-workers",
        "workforce-teams",
        "rate-limit-buckets",
        "ops-alert-acks",
        "ops-error-groups",
        "ops-audit",
    }.issubset(DEFAULT_TABLE_SUFFIXES)


def test_photo_lifecycle_retains_noncurrent_versions_and_aborts_multipart_uploads():
    rule = _s3_lifecycle()["Rules"][0]
    assert rule["Status"] == "Enabled"
    assert rule["Filter"]["Prefix"] == "reports/photos/"
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7
    orphan = _s3_lifecycle()["Rules"][1]
    assert orphan["ID"] == "OrphanReportPhotoCleanup"
    assert orphan["Filter"]["And"]["Tags"] == [{"Key": "upload-state", "Value": "orphan"}]
    assert orphan["Expiration"]["Days"] == 2


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
        "OrphanReportPhotoCleanup",
        "RedactedDerivativeVersionRetention",
    ]
    assert merged["Rules"][1]["Status"] == "Enabled"


def test_photo_lifecycle_health_requires_expected_rule():
    rule = _s3_lifecycle()["Rules"][0]
    assert rule["ID"] == "ReportPhotoVersionRetention"
    assert rule["Filter"]["Prefix"] == "reports/photos/"
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90
    derivative = _s3_lifecycle()["Rules"][2]
    assert derivative["ID"] == "RedactedDerivativeVersionRetention"
    assert derivative["Filter"]["Prefix"] == "reports/redacted/"
    assert derivative["NoncurrentVersionExpiration"]["NoncurrentDays"] == 90


def test_apply_enforces_encryption_and_complete_public_access_block():
    class Dynamo:
        pass

    class S3:
        def __init__(self):
            self.encryption = None
            self.public = None

        def put_bucket_versioning(self, **kwargs):
            pass

        def put_bucket_encryption(self, **kwargs):
            self.encryption = kwargs["ServerSideEncryptionConfiguration"]

        def put_public_access_block(self, **kwargs):
            self.public = kwargs["PublicAccessBlockConfiguration"]

        def get_bucket_lifecycle_configuration(self, **kwargs):
            return {"Rules": []}

        def put_bucket_lifecycle_configuration(self, **kwargs):
            pass

    s3 = S3()
    apply(Dynamo(), s3, {"dynamodb": []}, "private-reports")
    assert s3.encryption["Rules"][0]["ApplyServerSideEncryptionByDefault"] == {
        "SSEAlgorithm": "AES256"
    }
    assert all(s3.public.values())

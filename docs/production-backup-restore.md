# Production backup and restore runbook

This is the operator handoff for issue #187. It protects the persistent MVP
scope: tickets, users, ticket status history, audit history, AI outputs,
duplicate groups, municipalities, departments, categories, counters, and report
photos in S3.

## Recovery objectives

- RPO: 5 minutes for DynamoDB writes after PITR is enabled. S3 report photos have
  version-level recovery; a completed versioned write is recoverable immediately.
- RTO: 60 minutes for a single-table restore and 4 hours for a full application
  restore, excluding AWS service incidents and credential recovery.
- Restores always use new DynamoDB table names and an isolated S3 prefix. Never
  restore over active names.

## Enable and verify controls

From `backend/`, with production credentials and an empty
`DYNAMODB_ENDPOINT_URL`:

```bash
python scripts/backup/backup_controls.py --output backup-evidence/latest.json
python scripts/backup/backup_controls.py --apply --output backup-evidence/latest.json
python scripts/backup/backup_controls.py --output backup-evidence/latest.json
```

The final command must report PITR enabled for every existing persistent table,
S3 versioning enabled, AES-256 default encryption, all four S3 public-access
blocks, and a lifecycle rule retaining noncurrent report-photo versions for 90
days. The command exits non-zero when protection is missing, making it suitable
for a deployment gate and scheduled alert job.

## Isolated restore test

Dry-run first, then execute with a unique target:

```bash
python scripts/backup/restore_isolated.py \
  --source-table baladiguard-tickets \
  --target-table isolated-tickets-20260801-restore \
  --bucket "$AWS_S3_BUCKET" \
  --target-prefix restore-tests 

python scripts/backup/restore_isolated.py \
  --source-table baladiguard-tickets \
  --target-table isolated-tickets-20260801-restore \
  --bucket "$AWS_S3_BUCKET" \
  --target-prefix restore-tests \
  --execute | tee backup-evidence/restore-20260801.json
```

Validate the restored table with read-only queries before deleting the isolated
table. Validate that the copied photo versions can be read from the generated
`restore-tests/<run-id>/` prefix. Exercise the following before recording a
successful restore: delete a test item from the isolated table, restore it again
from PITR, and copy a known-good S3 version over a deliberately corrupted test
copy. Never perform these actions against production names or prefixes.

## Alerting and permissions

Run the audit command on a schedule (at least hourly) from a deployment or
operations role and alert on a non-zero exit code. Route the alert to the
on-call channel through the existing deployment scheduler/SNS integration. A
production control failure must page the operator; it must not be silently
logged.

The runtime application role has no backup mutation permissions. The backup
operator role is separate and should contain only:

- `dynamodb:DescribeTable`, `dynamodb:ListTables`,
  `dynamodb:DescribeContinuousBackups`, `dynamodb:UpdateContinuousBackups`,
  `dynamodb:RestoreTableToPointInTime` on the `baladiguard-*` tables.
- `s3:GetBucketVersioning`, `GetBucketEncryption`, `GetPublicAccessBlock`,
  `GetLifecycleConfiguration`, `PutBucketVersioning`, `PutBucketEncryption`,
  `PutPublicAccessBlock`, and `PutLifecycleConfiguration` on the report-photo
  bucket.
- `s3:ListBucket`, `s3:GetObjectVersion`, and `s3:PutObject` limited to
  `reports/photos/*` for source reads and `restore-tests/*` for isolated restore
  writes. Replace the `${AWS::Region}` and `${REPORT_PHOTO_BUCKET}` placeholders
  in `infra/backup/backup-operator-policy.json` before attaching it.

Do not grant `dynamodb:DeleteTable`, `s3:DeleteBucket`, or broad object deletion
to the backup operator role. Keep the latest JSON audit and restore evidence in
the protected operations evidence store, with a link added to the deployment
handoff for each quarterly restore test.

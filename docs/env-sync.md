# Local environment sync (AWS Secrets Manager)

Issue **#124**: stop sharing `.env` files over WhatsApp. The approved team
configuration lives in **AWS Secrets Manager**. A repo script pulls it into the
correct local files, and owners can push updates **without opening the AWS Console**.

The secret stores **full file text** for each target, so comments, blank lines,
key order, and quoting are preserved across push/pull.

## What gets synced

| Local path | Typical contents |
|---|---|
| `.env` | Shared AWS region, keys, S3 bucket, Location index |
| `backend/.env` | DynamoDB / Bedrock / backend settings |
| `mobile/.env` | Expo API URL and mock flags |
| `admin/.env` | Vite API URL and mock flags |

Default secret name: `baladiguard/local-dev/env` (override with `--secret-id` or
`ENV_SYNC_SECRET_ID`).

All four files are required in the secret bundle. A partial secret fails loudly.

## One-time AWS access

Each teammate needs AWS credentials that can at least:

- `secretsmanager:GetSecretValue` on `baladiguard/local-dev/env`

Owners who update the shared bundle also need:

- `secretsmanager:PutSecretValue`
- `secretsmanager:CreateSecret` (first push only)

Example IAM policy (attach to the team IAM user/role):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BaladiGuardEnvSyncReadWrite",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:baladiguard/local-dev/env*"
    },
    {
      "Sid": "BaladiGuardEnvSyncCreateOnce",
      "Effect": "Allow",
      "Action": ["secretsmanager:CreateSecret"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "secretsmanager:Name": "baladiguard/local-dev/env"
        }
      }
    }
  ]
}
```

Readers-only teammates can omit `PutSecretValue` / `CreateSecret`.

Configure AWS access in one of these ways:

1. `aws configure` / an IAM profile (`--profile your-profile`), or
2. Keep `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in the root `.env`. By default the
   script may copy those keys into process env for the boto3 session
   (`--no-bootstrap-env` disables that). Precedence: existing process env /
   profile wins over file bootstrap.

## Daily usage (pull)

Windows:

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py
```

macOS / Linux:

```bash
backend/.venv/bin/python scripts/sync_env.py
```

This writes/updates all four local env files. Secret values are never printed.

`EXPO_PUBLIC_API_BASE_URL` is preserved on pull when already set locally (phone LAN IP
is not overwritten by `localhost`).

A small gitignored `.env.sync-meta.json` records the last synced secret hash/version
for safer pushes.

## Updating secrets without the AWS Console (push)

When AWS keys or shared config change:

1. Edit the local env files as usual.
2. Preview (optional):

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py --push --dry-run
```

3. Push:

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py --push
```

That **creates** the secret the first time, or **updates** it afterward.

Machine-specific values such as `EXPO_PUBLIC_API_BASE_URL` are normalized to the
`mobile/.env.example` default on push so a LAN IP is never published as the team
default.

### Concurrency / single-writer

Treat Secrets Manager as a single source of truth with a **single writer at a time**.
If the remote secret changed since your last pull/push, push refuses unless you pass
`--force`. Prefer: pull → reconcile → push.

## First-time bootstrap for the team

1. One owner prepares complete local files from the `*.env.example` templates and
   fills approved values.
2. Owner runs `--push` once to create `baladiguard/local-dev/env`.
3. Everyone else configures AWS access and runs the pull command.
4. Stop sending `.env` files over WhatsApp / chat.

## Safety rules

- Local `.env` files stay gitignored — never commit them.
- The script never logs secret values.
- Missing credentials, missing/incomplete secret, or denied IAM access fail with a clear error.
- Auth failures (`UnrecognizedClientException`) are reported as bad credentials, not missing IAM grants.
- Writes use a temp file + replace so a crash does not leave a half-written env file.
- Bundles over the Secrets Manager 64 KB `SecretString` limit fail with a clear message.

## Related docs

- [cloud-setup.md](./cloud-setup.md) — what the cloud env values mean
- Root / package `*.env.example` — non-secret templates committed to Git

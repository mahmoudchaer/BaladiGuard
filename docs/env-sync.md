# Local environment sync (AWS Secrets Manager)

Issue **#124**: stop sharing `.env` files over WhatsApp. The approved team
configuration lives in **AWS Secrets Manager**. A repo script pulls it into the
correct local files, and owners can push updates **without opening the AWS Console**.

## What gets synced

| Local path | Typical contents |
|---|---|
| `.env` | Shared AWS region, keys, S3 bucket, Location index |
| `backend/.env` | DynamoDB / Bedrock / backend settings |
| `mobile/.env` | Expo API URL and mock flags |
| `admin/.env` | Vite API URL and mock flags |

Default secret name: `baladiguard/local-dev/env` (override with `--secret-id` or
`ENV_SYNC_SECRET_ID`).

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
      "Sid": "BaladiGuardEnvSync",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:CreateSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:baladiguard/local-dev/env*"
    }
  ]
}
```

Readers-only teammates can omit `PutSecretValue` and `CreateSecret`.

Configure AWS access in one of these ways:

1. `aws configure` / an IAM profile (`--profile your-profile`), or
2. Keep `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in the root `.env` (the sync
   script can bootstrap from that for the first push/pull).

Teammates who only pull still need IAM permission on the shared secret.

## Daily usage (pull)

From the repo root, using the backend virtualenv (has `boto3`):

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py
```

On macOS/Linux:

```bash
backend/.venv/bin/python scripts/sync_env.py
```

This writes/updates the four local env files. Secret values are never printed.

Machine-specific values such as `EXPO_PUBLIC_API_BASE_URL` are preserved on pull
when already set locally (so a phone LAN IP is not overwritten by `localhost`).

## Updating secrets without the AWS Console (push)

When AWS keys or shared config change:

1. Edit the local env files as usual.
2. Push them to Secrets Manager:

```bash
backend\.venv\Scripts\python.exe scripts\sync_env.py --push
```

That **creates** the secret the first time, or **updates** it afterward. No Console
clicking required.

Then tell the team to re-run the pull command.

## First-time bootstrap for the team

1. One owner prepares complete local files from the `*.env.example` templates and
   fills approved values.
2. Owner runs `--push` once to create `baladiguard/local-dev/env`.
3. Everyone else configures AWS CLI access and runs the pull command.
4. Stop sending `.env` files over WhatsApp / chat.

## Safety rules

- Local `.env` files stay gitignored — never commit them.
- The script never logs secret values.
- Missing credentials, missing secret, or denied IAM access fail with a clear error.
- Writes use a temp file + replace so a crash does not leave a half-written env file.

## Related docs

- [cloud-setup.md](./cloud-setup.md) — what the cloud env values mean
- Root / package `*.env.example` — non-secret templates committed to Git

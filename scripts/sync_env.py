#!/usr/bin/env python3
"""Sync local BaladiGuard .env files with AWS Secrets Manager (issue #124).

Pull (default): download the approved team env bundle and write local files.
Push: upload the current local env files to Secrets Manager (no AWS Console needed).

Examples:
  python scripts/sync_env.py
  python scripts/sync_env.py --push
  python scripts/sync_env.py --secret-id baladiguard/local-dev/env --region us-east-1

Never prints secret values. Requires AWS credentials via the normal boto3 chain
(environment variables, shared credentials file, or IAM role) — not via WhatsApp.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound
except ImportError:  # pragma: no cover - clear setup error for teammates
    print(
        "ERROR: boto3 is required. From the repo root run:\n"
        "  backend\\.venv\\Scripts\\python.exe -m pip install boto3\n"
        "or use the backend virtualenv Python to run this script.",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SECRET_ID = "baladiguard/local-dev/env"
DEFAULT_REGION = "us-east-1"
BUNDLE_VERSION = 1

# Relative paths written/read under the repo root.
ENV_TARGETS: tuple[str, ...] = (
    ".env",
    "backend/.env",
    "mobile/.env",
    "admin/.env",
)

# On pull, keep an existing local value for these keys (machine-specific).
LOCAL_PRESERVE_KEYS: frozenset[str] = frozenset(
    {
        "EXPO_PUBLIC_API_BASE_URL",
    }
)


class EnvSyncError(RuntimeError):
    """User-facing sync failure with a clear message (no secret values)."""


def bootstrap_aws_credentials_from_local_env(repo_root: Path) -> None:
    """If the process has no AWS keys yet, load them from local project env files.

    This covers the first push from an existing WhatsApp-era `.env` without requiring
    a separate `aws configure` step. Values are never printed.
    """
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return

    merged: dict[str, str] = {}
    for relative in (".env", "backend/.env"):
        merged.update(parse_env_file(repo_root / relative))

    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "AWS_DEFAULT_REGION"):
        value = merged.get(key, "").strip()
        if value and not os.getenv(key):
            os.environ[key] = value


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines; ignore blanks and comments."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def render_env_file(values: dict[str, str], *, header: str) -> str:
    lines = [header.rstrip(), ""]
    for key in sorted(values):
        lines.append(f"{key}={values[key]}")
    lines.append("")
    return "\n".join(lines)


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def merge_pull_values(remote: dict[str, str], local: dict[str, str]) -> dict[str, str]:
    """Remote managed keys win, except LOCAL_PRESERVE_KEYS already set locally."""
    merged = dict(local)
    for key, value in remote.items():
        if key in LOCAL_PRESERVE_KEYS and key in local and local[key].strip():
            continue
        merged[key] = value
    return merged


def collect_local_bundle(repo_root: Path) -> dict[str, dict[str, str]]:
    files: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for relative in ENV_TARGETS:
        path = repo_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        files[relative] = parse_env_file(path)
    if missing:
        raise EnvSyncError(
            "Cannot push — missing local env file(s): "
            + ", ".join(missing)
            + ". Create them from the matching *.env.example files first, or pull once."
        )
    if not any(files.values()):
        raise EnvSyncError("Cannot push — local env files exist but contain no KEY=VALUE entries.")
    return files


def build_bundle(files: dict[str, dict[str, str]]) -> dict[str, Any]:
    return {"version": BUNDLE_VERSION, "files": files}


def parse_bundle(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    if not isinstance(payload, dict):
        raise EnvSyncError("Secret payload is not a JSON object.")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise EnvSyncError(
            "Secret payload is missing a non-empty 'files' object. "
            "Expected keys like '.env', 'backend/.env', 'mobile/.env', 'admin/.env'."
        )
    parsed: dict[str, dict[str, str]] = {}
    for relative, values in files.items():
        if relative not in ENV_TARGETS:
            raise EnvSyncError(
                f"Secret contains unsupported env path '{relative}'. "
                f"Allowed: {', '.join(ENV_TARGETS)}"
            )
        if not isinstance(values, dict):
            raise EnvSyncError(f"Secret entry for '{relative}' must be an object of KEY=VALUE pairs.")
        cleaned: dict[str, str] = {}
        for key, value in values.items():
            if not isinstance(key, str) or not key.strip():
                raise EnvSyncError(f"Invalid key under '{relative}'.")
            if value is None:
                cleaned[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                cleaned[key] = str(value)
            else:
                raise EnvSyncError(f"Unsupported value type for '{relative}' / '{key}'.")
        parsed[relative] = cleaned
    return parsed


def secrets_client(region: str, profile: str | None):
    session_kwargs: dict[str, str] = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    try:
        session = boto3.Session(**session_kwargs)
        return session.client("secretsmanager")
    except ProfileNotFound as exc:
        raise EnvSyncError(f"AWS profile not found: {exc}") from exc
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "Unable to create an AWS session. Configure credentials with "
            "`aws configure`, environment variables, or --profile."
        ) from exc


def fetch_secret_bundle(client: Any, secret_id: str) -> dict[str, dict[str, str]]:
    try:
        response = client.get_secret_value(SecretId=secret_id)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        if code in {"ResourceNotFoundException", "SecretsManager.ResourceNotFoundException"}:
            raise EnvSyncError(
                f"Secret '{secret_id}' was not found. "
                "Create it once with: python scripts/sync_env.py --push"
            ) from exc
        if code in {"AccessDeniedException", "UnrecognizedClientException"}:
            raise EnvSyncError(
                f"Access denied reading secret '{secret_id}' ({code}). "
                "Ask a project owner to grant secretsmanager:GetSecretValue."
            ) from exc
        raise EnvSyncError(f"Failed to read secret '{secret_id}' ({code}).") from exc
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "AWS credentials are missing or invalid. Configure the AWS CLI or export "
            "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY for an account that can read the secret."
        ) from exc

    raw = response.get("SecretString")
    if not raw:
        raise EnvSyncError(f"Secret '{secret_id}' has no SecretString payload.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnvSyncError(f"Secret '{secret_id}' is not valid JSON.") from exc
    return parse_bundle(payload)


def put_secret_bundle(client: Any, secret_id: str, bundle: dict[str, Any]) -> str:
    """Create or update the secret. Returns 'created' or 'updated'."""
    body = json.dumps(bundle, separators=(",", ":"), sort_keys=True)
    try:
        client.put_secret_value(SecretId=secret_id, SecretString=body)
        return "updated"
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "AWS credentials are missing or invalid while writing the secret. "
            "Set AWS keys in the root `.env` / `backend/.env`, run `aws configure`, "
            "or pass --profile."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        if code not in {"ResourceNotFoundException", "SecretsManager.ResourceNotFoundException"}:
            if code in {"AccessDeniedException", "UnrecognizedClientException"}:
                raise EnvSyncError(
                    f"Access denied writing secret '{secret_id}' ({code}). "
                    "Push requires secretsmanager:PutSecretValue (and CreateSecret the first time)."
                ) from exc
            raise EnvSyncError(f"Failed to update secret '{secret_id}' ({code}).") from exc

    try:
        client.create_secret(
            Name=secret_id,
            Description="BaladiGuard approved local development environment bundle (issue #124).",
            SecretString=body,
        )
        return "created"
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "AWS credentials are missing or invalid while creating the secret."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "ClientError")
        if code in {"AccessDeniedException", "UnrecognizedClientException"}:
            raise EnvSyncError(
                f"Access denied creating secret '{secret_id}' ({code}). "
                "Ask an AWS admin for secretsmanager:CreateSecret / PutSecretValue."
            ) from exc
        raise EnvSyncError(f"Failed to create secret '{secret_id}' ({code}).") from exc


def pull_env_files(
    *,
    repo_root: Path,
    secret_id: str,
    region: str,
    profile: str | None,
) -> list[str]:
    bootstrap_aws_credentials_from_local_env(repo_root)
    client = secrets_client(region, profile)
    remote_files = fetch_secret_bundle(client, secret_id)
    written: list[str] = []
    for relative, remote_values in remote_files.items():
        path = repo_root / relative
        local_values = parse_env_file(path)
        merged = merge_pull_values(remote_values, local_values)
        header = (
            f"# Synced from AWS Secrets Manager ({secret_id}).\n"
            "# Do not commit this file. Re-run: python scripts/sync_env.py"
        )
        atomic_write_text(path, render_env_file(merged, header=header))
        written.append(relative)
    return written


def push_env_files(
    *,
    repo_root: Path,
    secret_id: str,
    region: str,
    profile: str | None,
) -> tuple[str, list[str]]:
    files = collect_local_bundle(repo_root)
    bootstrap_aws_credentials_from_local_env(repo_root)
    client = secrets_client(region, profile)
    action = put_secret_bundle(client, secret_id, build_bundle(files))
    return action, sorted(files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync BaladiGuard local .env files with AWS Secrets Manager.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Upload local .env files to Secrets Manager (create or update). Default is pull.",
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("ENV_SYNC_SECRET_ID", DEFAULT_SECRET_ID),
        help=f"Secrets Manager secret id/name (default: {DEFAULT_SECRET_ID}).",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", DEFAULT_REGION),
        help=f"AWS region (default: {DEFAULT_REGION} or AWS_REGION).",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="Optional AWS shared-credentials profile name.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()

    try:
        if args.push:
            action, paths = push_env_files(
                repo_root=repo_root,
                secret_id=args.secret_id,
                region=args.region,
                profile=args.profile,
            )
            print(f"OK: secret {action}: {args.secret_id}")
            print("Uploaded env files:")
            for relative in paths:
                print(f"  - {relative}")
            print("Teammates can refresh with: python scripts/sync_env.py")
            return 0

        written = pull_env_files(
            repo_root=repo_root,
            secret_id=args.secret_id,
            region=args.region,
            profile=args.profile,
        )
        print(f"OK: pulled env files from {args.secret_id}")
        for relative in written:
            print(f"  - {relative}")
        print("Secret values were written locally and were not printed.")
        return 0
    except EnvSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

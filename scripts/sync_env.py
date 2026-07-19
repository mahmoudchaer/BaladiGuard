#!/usr/bin/env python3
"""Sync local BaladiGuard .env files with AWS Secrets Manager (issue #124).

Pull (default): download the approved team env bundle and write local files.
Push: upload the current local env files to Secrets Manager (no AWS Console needed).

The secret stores **full file text** (version 2) so comments, blank lines, key order,
and quoting are preserved across push/pull.

Examples:
  python scripts/sync_env.py
  python scripts/sync_env.py --push
  python scripts/sync_env.py --push --dry-run
  python scripts/sync_env.py --secret-id baladiguard/local-dev/env --region us-east-1

Never prints secret values. Requires AWS credentials via the normal boto3 chain
(environment variables, shared credentials file, or IAM role) — not via WhatsApp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SECRET_ID = "baladiguard/local-dev/env"
DEFAULT_REGION = "us-east-1"
BUNDLE_VERSION = 2
# Secrets Manager SecretString soft limit is 65536 bytes.
SECRET_STRING_MAX_BYTES = 65536
SYNC_META_NAME = ".env.sync-meta.json"

# Relative paths written/read under the repo root.
ENV_TARGETS: tuple[str, ...] = (
    ".env",
    "backend/.env",
    "mobile/.env",
    "admin/.env",
)

# Machine-specific keys: keep local values on pull; never publish local values on push
# (replaced with the matching *.env.example default when present).
LOCAL_PRESERVE_KEYS: frozenset[str] = frozenset(
    {
        "EXPO_PUBLIC_API_BASE_URL",
    }
)

_ASSIGNMENT_RE = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?)(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<sep>\s*=\s*)(?P<value>.*)$"
)


class EnvSyncError(RuntimeError):
    """User-facing sync failure with a clear message (no secret values)."""


def _require_boto3():
    try:
        import boto3
        from botocore.exceptions import (
            BotoCoreError,
            ClientError,
            NoCredentialsError,
            ProfileNotFound,
        )
    except ImportError as exc:  # pragma: no cover
        raise EnvSyncError(
            "boto3 is required. From the repo root run:\n"
            "  backend/.venv/bin/python -m pip install boto3\n"
            "  backend\\.venv\\Scripts\\python.exe -m pip install boto3\n"
            "or use the backend virtualenv Python to run this script."
        ) from exc
    return boto3, BotoCoreError, ClientError, NoCredentialsError, ProfileNotFound


def parse_env_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE assignments from env file text (comments/blank ignored)."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        match = _ASSIGNMENT_RE.match(raw_line)
        if not match:
            continue
        key = match.group("key")
        value = match.group("value").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_text(path.read_text(encoding="utf-8"))


def format_env_value(value: str) -> str:
    """Quote values that would be ambiguous or corrupted without quotes."""
    if value == "":
        return ""
    needs_quotes = (
        any(ch.isspace() for ch in value)
        or value.startswith("#")
        or "#" in value
        or "=" in value
        or value.startswith('"')
        or value.startswith("'")
    )
    if not needs_quotes:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_key(text: str, key: str, value: str) -> str:
    """Set key=value in env text, preserving other lines/comments/order when possible."""
    formatted = format_env_value(value)
    lines = text.splitlines()
    replaced = False
    out: list[str] = []
    for line in lines:
        match = _ASSIGNMENT_RE.match(line)
        if match and match.group("key") == key:
            out.append(f"{match.group('prefix')}{key}{match.group('sep')}{formatted}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={formatted}")
    return "\n".join(out) + ("\n" if text.endswith("\n") or not text else "\n")


def apply_preserve_keys(content: str, local_values: dict[str, str]) -> str:
    updated = content
    for key in LOCAL_PRESERVE_KEYS:
        local_value = local_values.get(key, "").strip()
        if local_value:
            updated = upsert_env_key(updated, key, local_value)
    return updated


def normalize_preserve_keys_for_push(
    content: str, example_values: dict[str, str]
) -> str:
    """Replace machine-specific keys with example defaults before publishing."""
    updated = content
    for key in LOCAL_PRESERVE_KEYS:
        if key in example_values:
            updated = upsert_env_key(updated, key, example_values[key])
        else:
            # Drop the assignment line entirely if example has no default.
            lines = []
            for line in updated.splitlines():
                match = _ASSIGNMENT_RE.match(line)
                if match and match.group("key") == key:
                    continue
                lines.append(line)
            updated = "\n".join(lines) + ("\n" if updated.endswith("\n") else "")
    return updated


def example_path_for(repo_root: Path, relative: str) -> Path:
    if relative == ".env":
        return repo_root / ".env.example"
    # backend/.env -> backend/.env.example
    return repo_root / f"{relative}.example"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def sync_meta_path(repo_root: Path) -> Path:
    return repo_root / SYNC_META_NAME


def read_sync_meta(repo_root: Path) -> dict[str, Any]:
    path = sync_meta_path(repo_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_sync_meta(
    repo_root: Path, *, secret_id: str, content_hash: str, version_id: str | None
) -> None:
    payload = {
        "secretId": secret_id,
        "contentHash": content_hash,
        "versionId": version_id,
    }
    atomic_write_text(sync_meta_path(repo_root), json.dumps(payload, indent=2) + "\n")


def content_hash(secret_string: str) -> str:
    return hashlib.sha256(secret_string.encode("utf-8")).hexdigest()


def bootstrap_aws_credentials_from_local_env(repo_root: Path) -> list[str]:
    """Optionally load AWS_* from local env files into os.environ.

    Returns the list of keys that were injected (never values).
    """
    if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
        return []

    merged: dict[str, str] = {}
    for relative in (".env", "backend/.env"):
        merged.update(parse_env_file(repo_root / relative))

    injected: list[str] = []
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        value = merged.get(key, "").strip()
        if value and not os.getenv(key):
            os.environ[key] = value
            injected.append(key)
    return injected


def resolve_region(cli_region: str | None, repo_root: Path) -> str:
    """Resolve AWS region after optional local-env bootstrap."""
    if cli_region:
        return cli_region
    if os.getenv("AWS_REGION"):
        return os.environ["AWS_REGION"]
    if os.getenv("AWS_DEFAULT_REGION"):
        return os.environ["AWS_DEFAULT_REGION"]
    for relative in (".env", "backend/.env"):
        values = parse_env_file(repo_root / relative)
        for key in ("AWS_REGION", "AWS_DEFAULT_REGION"):
            if values.get(key, "").strip():
                return values[key].strip()
    return DEFAULT_REGION


def collect_local_file_texts(repo_root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    missing: list[str] = []
    for relative in ENV_TARGETS:
        path = repo_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        text = path.read_text(encoding="utf-8")
        example_values = parse_env_file(example_path_for(repo_root, relative))
        files[relative] = normalize_preserve_keys_for_push(text, example_values)
    if missing:
        raise EnvSyncError(
            "Cannot push — missing local env file(s): "
            + ", ".join(missing)
            + ". Create them from the matching *.env.example files first, or pull once."
        )
    if not any(parse_env_text(text) for text in files.values()):
        raise EnvSyncError(
            "Cannot push — local env files exist but contain no KEY=VALUE entries."
        )
    return files


def build_bundle(files: dict[str, str]) -> dict[str, Any]:
    return {"version": BUNDLE_VERSION, "files": files}


def parse_bundle(payload: dict[str, Any]) -> dict[str, str]:
    """Return relative path -> full file text. Accepts v2 text or legacy v1 maps."""
    if not isinstance(payload, dict):
        raise EnvSyncError("Secret payload is not a JSON object.")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise EnvSyncError(
            "Secret payload is missing a non-empty 'files' object. "
            "Expected keys like '.env', 'backend/.env', 'mobile/.env', 'admin/.env'."
        )

    missing = [relative for relative in ENV_TARGETS if relative not in files]
    if missing:
        raise EnvSyncError(
            "Secret bundle is incomplete — missing file(s): "
            + ", ".join(missing)
            + ". An owner should re-run: python scripts/sync_env.py --push"
        )

    unexpected = [key for key in files if key not in ENV_TARGETS]
    if unexpected:
        raise EnvSyncError(
            f"Secret contains unsupported env path(s): {', '.join(sorted(unexpected))}. "
            f"Allowed: {', '.join(ENV_TARGETS)}"
        )

    parsed: dict[str, str] = {}
    for relative in ENV_TARGETS:
        entry = files[relative]
        if isinstance(entry, str):
            parsed[relative] = (
                entry if entry.endswith("\n") or entry == "" else entry + "\n"
            )
            continue
        if isinstance(entry, dict):
            # Legacy v1 key/value maps — reconstruct a simple file (lossy for comments).
            lines = [
                f"# Migrated from legacy env-sync bundle format for {relative}.",
                "# Re-push with the current script to preserve comments and ordering.",
                "",
            ]
            for key in sorted(entry):
                value = entry[key]
                if value is None:
                    text_value = ""
                elif isinstance(value, (str, int, float, bool)):
                    text_value = str(value)
                else:
                    raise EnvSyncError(
                        f"Unsupported value type for '{relative}' / '{key}'."
                    )
                lines.append(f"{key}={format_env_value(text_value)}")
            lines.append("")
            parsed[relative] = "\n".join(lines)
            continue
        raise EnvSyncError(
            f"Secret entry for '{relative}' must be a file string or legacy KEY=VALUE object."
        )
    return parsed


def secrets_client(region: str, profile: str | None):
    boto3, BotoCoreError, _ClientError, NoCredentialsError, ProfileNotFound = (
        _require_boto3()
    )
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


def _client_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return response.get("Error", {}).get("Code", "ClientError")
    return "ClientError"


def fetch_secret_record(
    client: Any, secret_id: str
) -> tuple[dict[str, str], str, str | None]:
    """Return (files, secret_string, version_id)."""
    _, BotoCoreError, ClientError, NoCredentialsError, _ProfileNotFound = (
        _require_boto3()
    )
    try:
        response = client.get_secret_value(SecretId=secret_id)
    except ClientError as exc:
        code = _client_error_code(exc)
        if code in {
            "ResourceNotFoundException",
            "SecretsManager.ResourceNotFoundException",
        }:
            raise EnvSyncError(
                f"Secret '{secret_id}' was not found. "
                "Create it once with: python scripts/sync_env.py --push"
            ) from exc
        if code == "AccessDeniedException":
            raise EnvSyncError(
                f"Access denied reading secret '{secret_id}'. "
                "Ask a project owner to grant secretsmanager:GetSecretValue."
            ) from exc
        if code == "UnrecognizedClientException":
            raise EnvSyncError(
                "AWS rejected the credentials (UnrecognizedClientException). "
                "Check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
                "(typo, revoked key, or wrong account)."
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
    return parse_bundle(payload), raw, response.get("VersionId")


def put_secret_bundle(
    client: Any, secret_id: str, bundle: dict[str, Any]
) -> tuple[str, str, str | None]:
    """Create or update the secret. Returns (action, secret_string, version_id)."""
    _, BotoCoreError, ClientError, NoCredentialsError, _ProfileNotFound = (
        _require_boto3()
    )
    body = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    body_bytes = len(body.encode("utf-8"))
    if body_bytes > SECRET_STRING_MAX_BYTES:
        raise EnvSyncError(
            f"Env bundle is {body_bytes} bytes; Secrets Manager SecretString limit is "
            f"{SECRET_STRING_MAX_BYTES}. Split or trim env files before pushing."
        )

    try:
        response = client.put_secret_value(SecretId=secret_id, SecretString=body)
        return "updated", body, response.get("VersionId")
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "AWS credentials are missing or invalid while writing the secret. "
            "Set AWS keys in the root `.env` / `backend/.env`, run `aws configure`, "
            "or pass --profile."
        ) from exc
    except ClientError as exc:
        code = _client_error_code(exc)
        if code not in {
            "ResourceNotFoundException",
            "SecretsManager.ResourceNotFoundException",
        }:
            if code == "AccessDeniedException":
                raise EnvSyncError(
                    f"Access denied writing secret '{secret_id}'. "
                    "Push requires secretsmanager:PutSecretValue (and CreateSecret the first time)."
                ) from exc
            if code == "UnrecognizedClientException":
                raise EnvSyncError(
                    "AWS rejected the credentials (UnrecognizedClientException). "
                    "Check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
                    "(typo, revoked key, or wrong account)."
                ) from exc
            raise EnvSyncError(
                f"Failed to update secret '{secret_id}' ({code})."
            ) from exc

    try:
        response = client.create_secret(
            Name=secret_id,
            Description="BaladiGuard approved local development environment bundle (issue #124).",
            SecretString=body,
        )
        return "created", body, response.get("VersionId")
    except (BotoCoreError, NoCredentialsError) as exc:
        raise EnvSyncError(
            "AWS credentials are missing or invalid while creating the secret."
        ) from exc
    except ClientError as exc:
        code = _client_error_code(exc)
        if code == "AccessDeniedException":
            raise EnvSyncError(
                f"Access denied creating secret '{secret_id}'. "
                "Ask an AWS admin for secretsmanager:CreateSecret / PutSecretValue."
            ) from exc
        if code == "UnrecognizedClientException":
            raise EnvSyncError(
                "AWS rejected the credentials (UnrecognizedClientException). "
                "Check AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
                "(typo, revoked key, or wrong account)."
            ) from exc
        raise EnvSyncError(f"Failed to create secret '{secret_id}' ({code}).") from exc


def ensure_push_concurrency(
    *,
    client: Any,
    secret_id: str,
    repo_root: Path,
    new_body: str,
    force: bool,
) -> None:
    """Refuse to clobber a remote secret that changed since our last pull/push."""
    try:
        _files, remote_body, remote_version = fetch_secret_record(client, secret_id)
    except EnvSyncError as exc:
        if "was not found" in str(exc):
            return
        raise

    if remote_body == new_body:
        return

    meta = read_sync_meta(repo_root)
    last_hash = meta.get("contentHash")
    last_version = meta.get("versionId")
    remote_hash = content_hash(remote_body)
    known_remote = (last_hash and last_hash == remote_hash) or (
        last_version and last_version == remote_version
    )
    if known_remote or force:
        return

    raise EnvSyncError(
        f"Remote secret '{secret_id}' has changed since your last pull/push "
        "(or this machine has no sync meta). Pull first, reconcile, then push — "
        "or pass --force to overwrite (single-writer / last-write-wins)."
    )


def pull_env_files(
    *,
    repo_root: Path,
    secret_id: str,
    region: str,
    profile: str | None,
    bootstrap_env: bool,
) -> list[str]:
    if bootstrap_env:
        bootstrap_aws_credentials_from_local_env(repo_root)
    client = secrets_client(region, profile)
    remote_files, secret_string, version_id = fetch_secret_record(client, secret_id)
    written: list[str] = []
    for relative, remote_text in remote_files.items():
        path = repo_root / relative
        local_values = parse_env_file(path)
        content = apply_preserve_keys(remote_text, local_values)
        atomic_write_text(path, content)
        written.append(relative)
    write_sync_meta(
        repo_root,
        secret_id=secret_id,
        content_hash=content_hash(secret_string),
        version_id=version_id,
    )
    return written


def push_env_files(
    *,
    repo_root: Path,
    secret_id: str,
    region: str,
    profile: str | None,
    bootstrap_env: bool,
    force: bool,
    dry_run: bool,
) -> tuple[str, list[str]]:
    files = collect_local_file_texts(repo_root)
    bundle = build_bundle(files)
    new_body = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    if len(new_body.encode("utf-8")) > SECRET_STRING_MAX_BYTES:
        raise EnvSyncError(
            f"Env bundle is {len(new_body.encode('utf-8'))} bytes; Secrets Manager "
            f"SecretString limit is {SECRET_STRING_MAX_BYTES}."
        )

    if dry_run:
        print("DRY RUN: would upload env files:")
        for relative in sorted(files):
            print(f"  - {relative}")
        print(f"Bundle size: {len(new_body.encode('utf-8'))} bytes")
        return "dry-run", sorted(files)

    if bootstrap_env:
        bootstrap_aws_credentials_from_local_env(repo_root)
    client = secrets_client(region, profile)
    ensure_push_concurrency(
        client=client,
        secret_id=secret_id,
        repo_root=repo_root,
        new_body=new_body,
        force=force,
    )
    action, secret_string, version_id = put_secret_bundle(client, secret_id, bundle)
    write_sync_meta(
        repo_root,
        secret_id=secret_id,
        content_hash=content_hash(secret_string),
        version_id=version_id,
    )
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
        "--dry-run",
        action="store_true",
        help="With --push, show which files would be uploaded without writing to AWS.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="With --push, overwrite the remote secret even if it changed since last sync.",
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("ENV_SYNC_SECRET_ID", DEFAULT_SECRET_ID),
        help=f"Secrets Manager secret id/name (default: {DEFAULT_SECRET_ID}).",
    )
    parser.add_argument(
        "--region",
        default=None,
        help=f"AWS region (default: AWS_REGION / local .env / {DEFAULT_REGION}).",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE"),
        help="Optional AWS shared-credentials profile name.",
    )
    parser.add_argument(
        "--no-bootstrap-env",
        action="store_true",
        help="Do not copy AWS_* keys from local .env files into process env.",
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
    bootstrap_env = not args.no_bootstrap_env

    try:
        injected: list[str] = []
        if bootstrap_env:
            injected = bootstrap_aws_credentials_from_local_env(repo_root)
            if injected and args.push and not args.dry_run:
                print(
                    "Note: loaded AWS credentials from local env files into process env "
                    f"for keys: {', '.join(injected)} "
                    "(use --no-bootstrap-env to disable)."
                )
        region = resolve_region(args.region, repo_root)

        if args.push:
            action, paths = push_env_files(
                repo_root=repo_root,
                secret_id=args.secret_id,
                region=region,
                profile=args.profile,
                bootstrap_env=False,  # already bootstrapped above for region resolution
                force=args.force,
                dry_run=args.dry_run,
            )
            if action == "dry-run":
                return 0
            print(f"OK: secret {action}: {args.secret_id}")
            print("Uploaded env files:")
            for relative in paths:
                print(f"  - {relative}")
            print("Teammates can refresh with: python scripts/sync_env.py")
            return 0

        if args.dry_run:
            raise EnvSyncError("--dry-run is only supported with --push.")

        written = pull_env_files(
            repo_root=repo_root,
            secret_id=args.secret_id,
            region=region,
            profile=args.profile,
            bootstrap_env=False,
        )
        print(f"OK: pulled env files from {args.secret_id}")
        for relative in written:
            print(f"  - {relative}")
        print(
            f"Wrote all {len(ENV_TARGETS)} env targets. Secret values were not printed."
        )
        return 0
    except EnvSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

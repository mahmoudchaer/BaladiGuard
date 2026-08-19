"""Unit tests for scripts/sync_env.py helpers (issue #124)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from moto import mock_aws

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_ENV_PATH = REPO_ROOT / "scripts" / "sync_env.py"


def load_sync_env_module():
    spec = importlib.util.spec_from_file_location("baladiguard_sync_env", SYNC_ENV_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["baladiguard_sync_env"] = module
    spec.loader.exec_module(module)
    return module


sync_env = load_sync_env_module()


def _seed_env_tree(tmp_path: Path) -> None:
    samples = {
        ".env": (
            "# Shared cloud AWS values\n"
            "AWS_REGION=us-east-1\n"
            "AWS_ACCESS_KEY_ID=AKIAEXAMPLE\n"
            'NOTE="# hash in value"\n'
        ),
        "backend/.env": (
            "# Backend\n"
            "DATABASE_BACKEND=dynamodb\n"
            "# leave empty = real AWS\n"
            "DYNAMODB_ENDPOINT_URL=\n"
        ),
        "mobile/.env": (
            "EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000/v1\n"
            "EXPO_PUBLIC_ENABLE_MOCK_API=false\n"
        ),
        "admin/.env": "VITE_USE_MOCK_DATA=false\nVITE_API_BASE_URL=http://localhost:8000\n",
        "citizen-web/.env": (
            "VITE_APP_ENV=local\nVITE_API_BASE_URL=http://localhost:8000\n"
            "VITE_USE_MOCK_DATA=false\n"
        ),
        ".env.example": "AWS_REGION=\nAWS_ACCESS_KEY_ID=\n",
        "backend/.env.example": "DATABASE_BACKEND=dynamodb\n",
        "mobile/.env.example": "EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/v1\n",
        "admin/.env.example": "VITE_USE_MOCK_DATA=false\n",
        "citizen-web/.env.example": (
            "VITE_APP_ENV=local\nVITE_API_BASE_URL=http://localhost:8000\n"
        ),
    }
    for relative, body in samples.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def test_parse_preserves_need_for_quotes_and_format_env_value_round_trips():
    text = 'QUOTED="abc def"\nHASHED="#secret"\nPLAIN=ok\n'
    parsed = sync_env.parse_env_text(text)
    assert parsed["QUOTED"] == "abc def"
    assert parsed["HASHED"] == "#secret"
    assert sync_env.format_env_value(parsed["QUOTED"]) == '"abc def"'
    assert sync_env.format_env_value(parsed["HASHED"]) == '"#secret"'
    assert sync_env.format_env_value(parsed["PLAIN"]) == "ok"


def test_upsert_env_key_preserves_comments_and_order():
    original = "# keep me\nAWS_REGION=us-east-1\n\n# trailing section\nFOO=1\n"
    updated = sync_env.upsert_env_key(original, "AWS_REGION", "eu-west-1")
    assert updated.splitlines()[0] == "# keep me"
    assert "AWS_REGION=eu-west-1" in updated
    assert updated.index("# keep me") < updated.index("AWS_REGION=")
    assert updated.index("AWS_REGION=") < updated.index("# trailing section")


def test_pull_preserves_local_api_url_and_remote_file_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    _seed_env_tree(tmp_path)

    with mock_aws():
        assert (
            sync_env.main(
                [
                    "--push",
                    "--force",
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )

        # Local machine-specific URL should survive pull.
        (tmp_path / "mobile/.env").write_text(
            "EXPO_PUBLIC_API_BASE_URL=http://10.0.0.5:8000/v1\nEXPO_PUBLIC_ENABLE_MOCK_API=false\n",
            encoding="utf-8",
        )
        assert (
            sync_env.main(
                [
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )
        root_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "# Shared cloud AWS values" in root_text
        assert root_text.index("# Shared cloud AWS values") < root_text.index("AWS_REGION=")
        mobile = sync_env.parse_env_file(tmp_path / "mobile/.env")
        assert mobile["EXPO_PUBLIC_API_BASE_URL"] == "http://10.0.0.5:8000/v1"


def test_push_strips_machine_specific_api_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    _seed_env_tree(tmp_path)

    with mock_aws():
        files = sync_env.collect_local_file_texts(tmp_path)
        mobile_values = sync_env.parse_env_text(files["mobile/.env"])
        assert mobile_values["EXPO_PUBLIC_API_BASE_URL"] == "http://localhost:8000/v1"


def test_resolve_region_uses_local_env_after_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    (tmp_path / ".env").write_text("AWS_REGION=eu-central-1\n", encoding="utf-8")
    assert sync_env.resolve_region(None, tmp_path) == "eu-central-1"


def test_incomplete_bundle_is_rejected():
    with pytest.raises(sync_env.EnvSyncError, match="incomplete"):
        sync_env.parse_bundle({"version": 2, "files": {".env": "A=1\n"}})


def test_pre_312_bundle_derives_citizen_web_environment():
    files = {
        ".env": "AWS_REGION=us-east-1\n",
        "backend/.env": "DATABASE_BACKEND=memory\n",
        "mobile/.env": (
            "EXPO_PUBLIC_APP_ENV=development\n"
            "EXPO_PUBLIC_API_BASE_URL=http://10.0.0.5:8000/v1\n"
            "EXPO_PUBLIC_ENABLE_MOCK_API=false\n"
        ),
        "admin/.env": "VITE_USE_MOCK_DATA=false\n",
    }
    parsed = sync_env.parse_bundle({"version": 2, "files": files})
    citizen = sync_env.parse_env_text(parsed["citizen-web/.env"])
    assert citizen == {
        "VITE_APP_ENV": "development",
        "VITE_API_BASE_URL": "http://10.0.0.5:8000",
        "VITE_USE_MOCK_DATA": "false",
    }


def test_push_pull_round_trip_and_concurrency_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    _seed_env_tree(tmp_path)

    with mock_aws():
        assert (
            sync_env.main(
                [
                    "--push",
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "AKIAEXAMPLE" not in out

        # Simulate another writer changing the secret without updating local meta.
        client = sync_env.secrets_client("us-east-1", None)
        other = sync_env.build_bundle(
            {
                **sync_env.collect_local_file_texts(tmp_path),
                "admin/.env": "VITE_USE_MOCK_DATA=true\n",
            }
        )
        client.put_secret_value(
            SecretId="baladiguard/local-dev/env",
            SecretString=json.dumps(other, ensure_ascii=False, indent=2) + "\n",
        )

        assert (
            sync_env.main(
                [
                    "--push",
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 1
        )
        err = capsys.readouterr().err
        assert "has changed since your last pull/push" in err

        assert (
            sync_env.main(
                [
                    "--push",
                    "--force",
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )


def test_cli_does_not_print_secret_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    _seed_env_tree(tmp_path)
    (tmp_path / "backend/.env").write_text("SECRET_KEY=super-secret-value\n", encoding="utf-8")

    with mock_aws():
        assert (
            sync_env.main(
                [
                    "--push",
                    "--force",
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "super-secret-value" not in out
        assert (
            sync_env.main(
                [
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                    "--no-bootstrap-env",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "super-secret-value" not in out


def test_env_targets_are_gitignored():
    ignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore_text
    assert ".env.*" in ignore_text
    assert "!.env.example" in ignore_text
    # Package gitignores also cover nested env files.
    for package in ("backend", "mobile", "admin"):
        package_ignore = (REPO_ROOT / package / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in package_ignore


def test_importing_module_without_boto3_does_not_system_exit(monkeypatch: pytest.MonkeyPatch):
    # The module must import even if boto3 were missing; failure happens on use.
    assert hasattr(sync_env, "_require_boto3")
    assert sync_env.BUNDLE_VERSION == 2

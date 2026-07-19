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


def test_parse_and_render_env_round_trip(tmp_path: Path):
    path = tmp_path / ".env"
    path.write_text(
        '# comment\nAWS_REGION=us-east-1\nEMPTY=\nQUOTED="abc def"\n',
        encoding="utf-8",
    )
    parsed = sync_env.parse_env_file(path)
    assert parsed["AWS_REGION"] == "us-east-1"
    assert parsed["EMPTY"] == ""
    assert parsed["QUOTED"] == "abc def"

    rendered = sync_env.render_env_file(parsed, header="# header")
    assert "AWS_REGION=us-east-1" in rendered
    assert rendered.startswith("# header")


def test_merge_pull_preserves_local_api_url():
    remote = {
        "AWS_REGION": "us-east-1",
        "EXPO_PUBLIC_API_BASE_URL": "http://localhost:8000/v1",
    }
    local = {"EXPO_PUBLIC_API_BASE_URL": "http://192.168.1.20:8000/v1"}
    merged = sync_env.merge_pull_values(remote, local)
    assert merged["AWS_REGION"] == "us-east-1"
    assert merged["EXPO_PUBLIC_API_BASE_URL"] == "http://192.168.1.20:8000/v1"


def test_atomic_write_and_pull_push_with_moto(tmp_path: Path, monkeypatch: pytest.Monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    for relative, body in {
        ".env": "AWS_REGION=us-east-1\nAWS_ACCESS_KEY_ID=AKIAEXAMPLE\n",
        "backend/.env": "DATABASE_BACKEND=dynamodb\n",
        "mobile/.env": "EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/v1\n",
        "admin/.env": "VITE_USE_MOCK_DATA=false\nVITE_API_BASE_URL=http://localhost:8000\n",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    with mock_aws():
        action, uploaded = sync_env.push_env_files(
            repo_root=tmp_path,
            secret_id="baladiguard/local-dev/env",
            region="us-east-1",
            profile=None,
        )
        assert action == "created"
        assert ".env" in uploaded

        # Corrupt local files, then pull should restore managed keys.
        (tmp_path / ".env").write_text("AWS_REGION=old\n", encoding="utf-8")
        written = sync_env.pull_env_files(
            repo_root=tmp_path,
            secret_id="baladiguard/local-dev/env",
            region="us-east-1",
            profile=None,
        )
        assert ".env" in written
        restored = sync_env.parse_env_file(tmp_path / ".env")
        assert restored["AWS_REGION"] == "us-east-1"
        assert restored["AWS_ACCESS_KEY_ID"] == "AKIAEXAMPLE"

        # Second push updates.
        action2, _ = sync_env.push_env_files(
            repo_root=tmp_path,
            secret_id="baladiguard/local-dev/env",
            region="us-east-1",
            profile=None,
        )
        assert action2 == "updated"


def test_missing_secret_has_clear_error(monkeypatch: pytest.Monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    with mock_aws():
        client = sync_env.secrets_client("us-east-1", None)
        with pytest.raises(sync_env.EnvSyncError, match="was not found"):
            sync_env.fetch_secret_bundle(client, "baladiguard/does-not-exist")


def test_parse_bundle_rejects_unknown_path():
    with pytest.raises(sync_env.EnvSyncError, match="unsupported env path"):
        sync_env.parse_bundle({"version": 1, "files": {"evil/.env": {"A": "1"}}})


def test_cli_pull_does_not_print_secret_values(
    tmp_path: Path,
    monkeypatch: pytest.Monkeypatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    for relative, body in {
        ".env": "AWS_SECRET_ACCESS_KEY=super-secret-value\n",
        "backend/.env": "SECRET_KEY=another-secret\n",
        "mobile/.env": "EXPO_PUBLIC_ENABLE_MOCK_API=false\n",
        "admin/.env": "VITE_USE_MOCK_DATA=false\n",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

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
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "super-secret-value" not in out
        assert "another-secret" not in out

        assert (
            sync_env.main(
                [
                    "--repo-root",
                    str(tmp_path),
                    "--secret-id",
                    "baladiguard/local-dev/env",
                    "--region",
                    "us-east-1",
                ]
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "super-secret-value" not in out
        assert "Secret values were written locally" in out
        # Ensure JSON shape stored is valid without printing it in CLI output.
        assert "files" in json.dumps(sync_env.build_bundle(sync_env.collect_local_bundle(tmp_path)))

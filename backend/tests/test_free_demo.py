import importlib.util
from pathlib import Path
import json
import pytest

spec = importlib.util.spec_from_file_location(
    "caregap_free_demo", Path(__file__).resolve().parents[2] / "infra/free-demo/start.py"
)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_demo_never_reuses_existing_data_or_external_processors(tmp_path):
    original = dict(
        DATABASE_URL="postgresql://must-not-open",
        STORAGE_DIR="/private/patient-vault",
        SECRET_KEY="must-not-reuse",
        S3_ACCESS_KEY_ID="must-not-send",
        SUMMARY_PROVIDER="http",
        SUMMARY_PROVIDER_APPROVED="true",
        KNOWLEDGE_MODE="approved_catalog",
        RENDER_EXTERNAL_URL="https://synthetic-example.onrender.com",
    )
    env = demo.demo_environment(original, tmp_path)
    assert env["DATABASE_URL"].startswith("sqlite:///") and tmp_path.as_posix() in env["DATABASE_URL"]
    assert env["STORAGE_DIR"] == str(tmp_path / "documents")
    assert env["SECRET_KEY"] != original["SECRET_KEY"] and len(env["SECRET_KEY"]) >= 32
    assert env["SUMMARY_PROVIDER"] == "extractive" and env["SUMMARY_PROVIDER_APPROVED"] == "false"
    assert env["S3_ACCESS_KEY_ID"] == "" and env["STORAGE_BACKEND"] == "local"
    assert env["DEMO_MODE"] == "true" and env["COOKIE_SECURE"] == "true"
    assert env["KNOWLEDGE_MODE"] == "disabled"
    assert json.loads(env["CORS_ORIGINS"]) == [original["RENDER_EXTERNAL_URL"]]
    assert original["DATABASE_URL"] == "postgresql://must-not-open"


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com/path",
        "https://example.com?secret=value",
        "javascript:alert(1)",
    ],
)
def test_demo_requires_explicit_valid_origin(tmp_path, origin):
    with pytest.raises(ValueError):
        demo.demo_environment(dict(RENDER_EXTERNAL_URL=origin), tmp_path)


def test_local_demo_uses_only_explicit_loopback_origin(tmp_path):
    env = demo.demo_environment(dict(CAREGAP_DEMO_ORIGIN="http://127.0.0.1:3600", PORT="10000"), tmp_path)
    assert env["COOKIE_SECURE"] == "false"
    with pytest.raises(ValueError):
        demo.demo_environment(dict(CAREGAP_DEMO_ORIGIN="http://127.0.0.1:3600", PORT="1"), tmp_path)

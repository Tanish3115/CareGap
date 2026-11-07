import importlib.util
import json
from pathlib import Path

import pytest
from app.config import Settings
from app.hosted import validate_hosted


def profile(**changes):
    values = dict(
        SECRET_KEY="isolated-hosting-test-key-with-more-than-32-characters",
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+psycopg://owner:password@db.example:5432/postgres?sslmode=require",
        COOKIE_SECURE=True,
        DEMO_MODE=False,
        CORS_ORIGINS=["https://caregap.example"],
        RATE_LIMIT_STORAGE_URI="rediss://default:password@redis.example:6379",
        STORAGE_BACKEND="s3",
        S3_PROVIDER="supabase",
        S3_ENDPOINT_URL="https://example.storage.supabase.co/storage/v1/s3",
        S3_ACCESS_KEY_ID="test-key",
        S3_SECRET_ACCESS_KEY="test-secret",
        S3_MANAGED_ENCRYPTION_VERIFIED=True,
        S3_ENCRYPTION_REVIEW_REFERENCE="test-review-only",
    )
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_hosting_profile_validates_offline():
    validate_hosted(profile())


@pytest.mark.parametrize(
    "changes",
    [
        {"S3_MANAGED_ENCRYPTION_VERIFIED": False},
        {"S3_ENCRYPTION_REVIEW_REFERENCE": " "},
        {"S3_PROVIDER": "generic"},
        {"S3_SERVER_SIDE_ENCRYPTION": "AES256"},
        {"RATE_LIMIT_STORAGE_URI": "redis://redis.example"},
        {"S3_ENDPOINT_URL": "https://example.storage.supabase.co.attacker.test/storage/v1/s3"},
        {"S3_ENDPOINT_URL": "http://example.storage.supabase.co/storage/v1/s3"},
        {"S3_ENDPOINT_URL": "https://example.storage.supabase.co/storage/v1/s3?x=y"},
    ],
)
def test_unreviewed_or_incompatible_storage_rejected(changes):
    with pytest.raises(ValueError):
        profile(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"DATABASE_URL": "postgresql+psycopg://owner:password@db.example/postgres"},
        {"COOKIE_SECURE": False},
        {"CORS_ORIGINS": ["https://*.example"]},
        {"CORS_ORIGINS": ["http://caregap.example"]},
        {"CORS_ORIGINS": []},
    ],
)
def test_hosted_transport_requirements(changes):
    with pytest.raises(ValueError):
        validate_hosted(profile(**changes))


def script(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparation_keeps_secrets_private_and_blocks_unfilled_config(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    folder = tmp_path / "infra/hosting"
    folder.mkdir(parents=True)
    for name in ("render.env.example", "vercel.env.example"):
        (folder / name).write_bytes((root / "infra/hosting" / name).read_bytes())
    preparation = script("prepare_hosting")
    monkeypatch.setattr(preparation, "ROOT", tmp_path)
    result = preparation.prepare()
    private = Path(result["preparation_directory"])
    from dotenv import dotenv_values

    secret = dotenv_values(private / "render.env")["SECRET_KEY"]
    assert len(secret) >= 64
    assert secret not in json.dumps(result)
    sql = (private / "supabase_public_schema_lockdown.sql").read_text()
    assert 'ALTER TABLE public."users" ENABLE ROW LEVEL SECURITY;' in sql
    assert "auth." not in sql and "storage." not in sql
    report = script("hosting_preflight").check(private / "render.env")
    assert not report["configuration_complete"]
    assert not report["data_transferred"]
    assert secret not in json.dumps(report)


def test_supabase_sdk_avoids_optional_checksum_headers(monkeypatch):
    import boto3
    from app.services import object_storage

    captured = {}
    monkeypatch.setattr(object_storage, "settings", profile())

    def client(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(boto3, "client", client)
    assert object_storage.S3PrivateObjectStore().client is not None
    assert captured["config"].request_checksum_calculation == "when_required"
    assert captured["config"].response_checksum_validation == "when_required"


def test_complete_preflight_still_requires_live_verification(tmp_path):
    values = profile().model_dump(mode="json")
    path = tmp_path / "render.env"
    selected = [
        "SECRET_KEY",
        "ENVIRONMENT",
        "DATABASE_URL",
        "COOKIE_SECURE",
        "DEMO_MODE",
        "CORS_ORIGINS",
        "RATE_LIMIT_STORAGE_URI",
        "STORAGE_BACKEND",
        "S3_PROVIDER",
        "S3_ENDPOINT_URL",
        "S3_REGION",
        "S3_BUCKET",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "S3_MANAGED_ENCRYPTION_VERIFIED",
        "S3_ENCRYPTION_REVIEW_REFERENCE",
    ]
    for name in ("RATE_LIMIT_STORAGE_URI", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"):
        values[name] = getattr(profile(), name).get_secret_value()
    path.write_text(
        "\n".join(
            name
            + "="
            + (json.dumps(values[name]) if isinstance(values[name], (list, bool)) else str(values[name]))
            for name in selected
        )
    )
    report = script("hosting_preflight").check(path)
    assert report["configuration_complete"]
    assert not report["cloud_connections_tested"]
    assert not report["bucket_privacy_verified"]

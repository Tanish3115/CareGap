"""Run migrations and API tests in a newly created synthetic PostgreSQL database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url, URL
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
config_values = dotenv_values(root / ".env")
base_url = (
    make_url(os.environ["CAREGAP_POSTGRES_URL"])
    if os.environ.get("CAREGAP_POSTGRES_URL")
    else URL.create(
        "postgresql+psycopg",
        username="caregap_user",
        password=config_values["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=int(config_values.get("POSTGRES_PORT", 55432)),
        database="postgres",
    )
)
name = "caregap_ci_" + uuid4().hex
maintenance = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with maintenance.connect() as connection:
    # Name is generated locally from a constant prefix and UUID hex only.
    connection.execute(text(f'CREATE DATABASE "{name}"'))
try:
    target = base_url.set(database=name).render_as_string(hide_password=False)
    os.environ.update(
        DATABASE_URL=target, ENVIRONMENT="test", SECRET_KEY="synthetic-postgres-test-key-not-for-deployment"
    )
    from alembic import command
    from alembic.config import Config

    config = Config(str(root / "backend" / "alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)
    # Check the migrated table before API fixtures recreate tables from models.
    # A Supabase Data API role must never inherit access to recovery credentials.
    migrated_engine = create_engine(target)
    try:
        with migrated_engine.connect() as connection:
            assert connection.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE oid = 'password_reset_tokens'::regclass")
            ).scalar_one(), "Recovery table must have row-level security"
            assert not connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_class c, "
                    "LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) a "
                    "WHERE c.oid = 'password_reset_tokens'::regclass AND a.grantee = 0)"
                )
            ).scalar_one(), "PUBLIC must not have recovery-table privileges"
            for role in connection.execute(
                text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            ).scalars():
                assert not connection.execute(
                    text(
                        "SELECT has_table_privilege(:role, 'password_reset_tokens', "
                        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
                    ),
                    {"role": role},
                ).scalar_one(), "Data API roles must not have recovery-table privileges"
            assert connection.execute(text("SELECT COUNT(*) FROM password_reset_tokens")).scalar_one() == 0
    finally:
        migrated_engine.dispose()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *sys.argv[1:]],
        cwd=root / "backend",
        env={**os.environ, "CAREGAP_TEST_DATABASE_URL": target},
    )
finally:
    with maintenance.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{name}"'))
    maintenance.dispose()
raise SystemExit(result.returncode)

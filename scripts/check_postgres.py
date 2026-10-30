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
base_url = make_url(os.environ["CAREGAP_POSTGRES_URL"]) if os.environ.get("CAREGAP_POSTGRES_URL") else URL.create(
    "postgresql+psycopg", username="caregap_user", password=config_values["POSTGRES_PASSWORD"],
    host="127.0.0.1", port=int(config_values.get("POSTGRES_PORT", 55432)), database="postgres")
name = "caregap_ci_" + uuid4().hex
maintenance = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with maintenance.connect() as connection:
    # Name is generated locally from a constant prefix and UUID hex only.
    connection.execute(text(f'CREATE DATABASE "{name}"'))
try:
    target = base_url.set(database=name).render_as_string(hide_password=False)
    os.environ.update(DATABASE_URL=target, ENVIRONMENT="test", SECRET_KEY="synthetic-postgres-test-key-not-for-deployment")
    from alembic import command
    from alembic.config import Config
    config = Config(str(root / "backend" / "alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root / "backend",
                            env={**os.environ, "CAREGAP_TEST_DATABASE_URL": target})
finally:
    with maintenance.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{name}"'))
    maintenance.dispose()
raise SystemExit(result.returncode)

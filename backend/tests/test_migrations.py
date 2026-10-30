from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect, text
import os
import subprocess
import sys
from app.config import settings
from app.database import Base


def test_migrations_match_models_and_preserve_baseline_rows(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration-test.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT full_name FROM users WHERE id='synthetic'")).scalar_one() == "Synthetic"
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "0001")
    assert "auth_sessions" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    engine.dispose()


def test_legacy_adoption_backs_up_and_preserves_records(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(root / "backend" / "alembic.ini"))
    command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(text("INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.com','test-hash','patient','Synthetic preservation test',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    backup = tmp_path / "backups"
    result = subprocess.run([sys.executable, str(root / "scripts" / "adopt_legacy_sqlite.py"), "--backup-directory", str(backup)],
                            env={**os.environ, "DATABASE_URL": url}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(list(backup.glob("*.db"))) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT full_name FROM users WHERE id='synthetic'")).scalar_one() == "Synthetic preservation test"
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0002"
    engine.dispose()


def test_legacy_adoption_rejects_unknown_schema(tmp_path):
    root = Path(__file__).resolve().parents[2]
    url = f"sqlite:///{(tmp_path / 'unknown.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unknown_layout (id INTEGER PRIMARY KEY)"))
    backup = tmp_path / "backups"
    result = subprocess.run([sys.executable, str(root / "scripts" / "adopt_legacy_sqlite.py"), "--backup-directory", str(backup)],
                            env={**os.environ, "DATABASE_URL": url}, capture_output=True, text=True)
    assert result.returncode != 0
    assert "no changes made" in result.stderr.lower()
    assert not backup.exists()
    assert inspect(engine).get_table_names() == ["unknown_layout"]
    engine.dispose()

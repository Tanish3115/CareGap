from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.database import Base


def test_password_reset_migration_preserves_existing_accounts_and_sessions(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'password-reset-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0019")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users(id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.test','original-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        db.execute(
            text(
                "INSERT INTO auth_sessions(id,user_id,expires_at) VALUES ('synthetic-session','synthetic','2030-01-01')"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0020"
        assert db.execute(text("SELECT hashed_password FROM users")).scalar_one() == "original-hash"
        assert db.execute(text("SELECT COUNT(*) FROM auth_sessions")).scalar_one() == 1
        assert compare_metadata(MigrationContext.configure(db), Base.metadata) == []
    command.downgrade(config, "0019")
    with engine.connect() as db:
        assert "password_reset_tokens" not in inspect(db).get_table_names()
        assert db.execute(text("SELECT COUNT(*) FROM auth_sessions")).scalar_one() == 1
    engine.dispose()

from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from app.config import settings


def test_pending_cleanup_prevents_downgrade_and_preserves_patient(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'cleanup-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO users(id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic-cleanup@example.test','test','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        db.execute(
            text(
                "INSERT INTO patients(id,user_id,patient_code,created_at) VALUES ('synthetic-patient','synthetic','A001',CURRENT_TIMESTAMP)"
            )
        )
        db.execute(
            text(
                "INSERT INTO file_deletions(id,patient_id,document_id,storage_key,storage_backend,sha256,status,attempts,next_attempt_at,created_at) VALUES ('synthetic-cleanup','synthetic-patient','synthetic-document','synthetic-patient/source.pdf','local','synthetic-checksum','pending',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    with pytest.raises(RuntimeError, match="Finish pending document file cleanup"):
        command.downgrade(config, "0018")
    with engine.begin() as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0019"
        assert db.execute(text("SELECT COUNT(*) FROM file_deletions")).scalar_one() == 1
        db.execute(text("UPDATE file_deletions SET status='done',storage_key='',sha256=''"))
    command.downgrade(config, "0018")
    command.upgrade(config, "head")
    with engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM patients")).scalar_one() == 1
        assert db.execute(text("SELECT COUNT(*) FROM file_deletions")).scalar_one() == 0
    engine.dispose()

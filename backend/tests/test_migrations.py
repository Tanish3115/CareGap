from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
import os
import subprocess
import sys
import re
import json
import pytest
from app.config import settings
from app.database import Base


def test_language_migration_preserves_preferences_and_refuses_lossy_downgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'language-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0017")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','language@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,patient_code,created_at) VALUES ('patient','synthetic','A001',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO notification_preferences (patient_id,version,enabled,channels,language) VALUES ('patient',7,1,'[\"in_app\",\"sms\"]','hi')"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert tuple(
            connection.execute(
                text("SELECT version,enabled,channels,language FROM notification_preferences")
            ).one()
        ) == (7, 1, '["in_app","sms"]', "hi")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    command.downgrade(config, "0017")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text("UPDATE notification_preferences SET language='kn'"))
    with pytest.raises(RuntimeError, match="discard language preferences"):
        command.downgrade(config, "0017")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT language FROM notification_preferences")).scalar_one() == "kn"
        # 0019 was safely removed before 0018 refused the lossy language downgrade.
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0018"
    engine.dispose()


def test_clinical_group_migration_snapshots_and_downgrades_without_broadening(tmp_path, monkeypatch):
    from app.core.clinical_resources import CLINICAL_RESOURCES

    url = f"sqlite:///{(tmp_path / 'clinical-groups.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0014")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','groups@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,patient_code,created_at) VALUES ('patient','synthetic','A001',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO doctors (id,user_id,license_number,specialization,verification_status,created_at) VALUES ('doctor','synthetic','SYNTHETIC','Test','verified',CURRENT_TIMESTAMP)"
            )
        )
        for identifier, clinical in [("restricted", 1), ("full", 1), ("missing", 1), ("documents", 0)]:
            connection.execute(
                text(
                    "INSERT INTO consent_grants (id,patient_id,doctor_id,scope,purpose,valid_from,valid_until,is_revoked,created_at,allow_upload,include_clinical_records,allow_clinical_write) VALUES (:id,'patient','doctor','all','Synthetic',CURRENT_TIMESTAMP,'2027-01-01',0,CURRENT_TIMESTAMP,0,:clinical,:clinical)"
                ),
                dict(id=identifier, clinical=clinical),
            )
        connection.execute(
            text(
                "INSERT INTO access_requests (id,patient_id,doctor_id,scope,purpose,duration_hours,allow_upload,status,created_at,include_clinical_records,allow_clinical_write) VALUES ('request','patient','doctor','all','Synthetic',24,0,'pending',CURRENT_TIMESTAMP,1,1)"
            )
        )
    command.upgrade(config, "head")
    with engine.begin() as connection:
        for table in ("consent_grants", "access_requests"):
            for (resources,) in connection.execute(
                text(f"SELECT clinical_resources FROM {table} WHERE include_clinical_records=1")
            ):
                assert set(json.loads(resources)) == CLINICAL_RESOURCES
        assert (
            connection.execute(
                text("SELECT clinical_resources FROM consent_grants WHERE id='documents'")
            ).scalar_one()
            is None
        )
        for table, identifier in [("consent_grants", "restricted"), ("access_requests", "request")]:
            connection.execute(
                text(f"UPDATE {table} SET clinical_resources=:resources WHERE id=:id"),
                dict(resources=json.dumps(["labs"]), id=identifier),
            )
        connection.execute(text("UPDATE consent_grants SET clinical_resources=NULL WHERE id='missing'"))
    command.downgrade(config, "0014")
    with engine.connect() as connection:
        assert tuple(
            connection.execute(
                text(
                    "SELECT include_clinical_records,allow_clinical_write FROM consent_grants WHERE id='restricted'"
                )
            ).one()
        ) == (0, 0)
        assert tuple(
            connection.execute(
                text(
                    "SELECT include_clinical_records,allow_clinical_write FROM consent_grants WHERE id='missing'"
                )
            ).one()
        ) == (0, 0)
        assert tuple(
            connection.execute(
                text("SELECT include_clinical_records,allow_clinical_write FROM access_requests")
            ).one()
        ) == (0, 0)
        assert tuple(
            connection.execute(
                text(
                    "SELECT include_clinical_records,allow_clinical_write FROM consent_grants WHERE id='full'"
                )
            ).one()
        ) == (1, 1)
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert tuple(
            connection.execute(
                text(
                    "SELECT include_clinical_records,clinical_resources FROM consent_grants WHERE id='restricted'"
                )
            ).one()
        ) == (0, None)
        assert connection.execute(text("SELECT COUNT(*) FROM consent_grants")).scalar_one() == 4
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    engine.dispose()


def test_migrations_match_models_and_preserve_baseline_rows(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration-test.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0001")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,created_at) VALUES ('original-patient-id','synthetic',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO medical_documents (id,patient_id,uploader_id,title,document_type,file_path,file_name,file_size,mime_type,sha256_hash,status,created_at,updated_at) VALUES ('original-document-id','original-patient-id','synthetic','Synthetic source','other','synthetic/file.pdf','file.pdf',123,'application/pdf','test-checksum','uploaded',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT full_name FROM users WHERE id='synthetic'")).scalar_one()
            == "Synthetic"
        )
        code = connection.execute(
            text("SELECT patient_code FROM patients WHERE id='original-patient-id'")
        ).scalar_one()
        assert re.fullmatch(r"[A-Z][0-9]{3}", code)
        assert (
            connection.execute(
                text("SELECT patient_id FROM medical_documents WHERE id='original-document-id'")
            ).scalar_one()
            == "original-patient-id"
        )
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
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.com','test-hash','patient','Synthetic preservation test',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    backup = tmp_path / "backups"
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "adopt_legacy_sqlite.py"), "--backup-directory", str(backup)],
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert len(list(backup.glob("*.db"))) == 1
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT full_name FROM users WHERE id='synthetic'")).scalar_one()
            == "Synthetic preservation test"
        )
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0019"
    engine.dispose()


def test_legacy_adoption_rejects_unknown_schema(tmp_path):
    root = Path(__file__).resolve().parents[2]
    url = f"sqlite:///{(tmp_path / 'unknown.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE unknown_layout (id INTEGER PRIMARY KEY)"))
    backup = tmp_path / "backups"
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "adopt_legacy_sqlite.py"), "--backup-directory", str(backup)],
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no changes made" in result.stderr.lower()
    assert not backup.exists()
    assert inspect(engine).get_table_names() == ["unknown_layout"]
    engine.dispose()


def test_clinical_migration_preserves_document_only_permissions(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'consent-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0004")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,patient_code,created_at) VALUES ('patient','synthetic','A001',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO doctors (id,user_id,license_number,specialization,verification_status,created_at) VALUES ('doctor','synthetic','SYNTHETIC','Test','verified',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO consent_grants (id,patient_id,doctor_id,scope,purpose,valid_from,valid_until,is_revoked,created_at,allow_upload) VALUES ('grant','patient','doctor','all','Synthetic',CURRENT_TIMESTAMP,'2027-01-01',0,CURRENT_TIMESTAMP,1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO access_requests (id,patient_id,doctor_id,scope,purpose,duration_hours,allow_upload,status,created_at) VALUES ('request','patient','doctor','all','Synthetic',24,1,'pending',CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        for table in ("consent_grants", "access_requests"):
            row = connection.execute(
                text(f"SELECT allow_upload,include_clinical_records,allow_clinical_write FROM {table}")
            ).one()
            assert tuple(row) == (1, 0, 0)
    engine.dispose()


def test_encounter_status_migration_preserves_existing_revisions_and_sources(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'status-migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0005")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES ('synthetic','synthetic@example.test','test-hash','patient','Synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,patient_code,created_at) VALUES ('patient','synthetic','A001',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO medical_documents (id,patient_id,uploader_id,title,document_type,file_path,file_name,file_size,mime_type,sha256_hash,status,created_at,updated_at) VALUES ('source','patient','synthetic','Synthetic source','other','synthetic/file.pdf','file.pdf',123,'application/pdf','test-checksum','uploaded',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO encounters (id,patient_id,created_by,version,created_at,updated_at) VALUES ('encounter','patient','synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO encounter_revisions (id,encounter_id,version,title,recorded_by,provenance,correction_reason,created_at,occurred_on,notes) VALUES ('revision','encounter',1,'Synthetic visit','synthetic','patient_reported','Initial record',CURRENT_TIMESTAMP,'2026-01-10','Original synthetic notes')"
            )
        )
        connection.execute(
            text("INSERT INTO encounter_sources (revision_id,document_id) VALUES ('revision','source')")
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert tuple(
            connection.execute(text("SELECT status,notes,version FROM encounter_revisions")).one()
        ) == ("active", "Original synthetic notes", 1)
        assert tuple(
            connection.execute(text("SELECT revision_id,document_id FROM encounter_sources")).one()
        ) == ("revision", "source")
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE encounter_revisions SET status='deleted'"))
    command.downgrade(config, "0005")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT notes FROM encounter_revisions")).scalar_one()
            == "Original synthetic notes"
        )
        assert connection.execute(text("SELECT COUNT(*) FROM encounter_sources")).scalar_one() == 1
    engine.dispose()


def test_four_character_migration_refuses_over_capacity_without_changing_ids(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'capacity.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(config, "0003")
    engine = create_engine(url)
    rows = [
        {
            "id": f"synthetic-{index}",
            "email": f"synthetic-capacity-{index}@example.com",
            "code": f"CG-{10_000_000 + index}",
        }
        for index in range(26_001)
    ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,hashed_password,role,full_name,is_active,created_at,updated_at) VALUES (:id,:email,'synthetic-hash','patient','Synthetic capacity test',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            ),
            rows,
        )
        connection.execute(
            text(
                "INSERT INTO patients (id,user_id,patient_code,created_at) VALUES (:id,:id,:code,CURRENT_TIMESTAMP)"
            ),
            rows,
        )
    with pytest.raises(RuntimeError, match="26,000"):
        command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM patients WHERE patient_code LIKE 'CG-%'")
            ).scalar_one()
            == 26_001
        )
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003"
    engine.dispose()

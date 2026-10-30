"""Back up and migrate the exact original six-table SQLite schema.

Stop the application first. Unknown schemas are rejected, never stamped blindly.
"""
import os
import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
os.chdir(root / "backend")
sys.path.insert(0, str(root / "backend"))
from app.config import settings
from app.database import Base
import app.models
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config


def adopt(backup_directory=None):
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "sqlite" or not url.database or not Path(url.database).is_file():
        raise SystemExit("This command only adopts an existing SQLite file. Use migrations directly for a fresh database.")
    engine = create_engine(url)
    inspector = inspect(engine)
    original_tables = {"users", "patients", "doctors", "medical_documents", "consent_grants", "audit_logs"}
    if set(inspector.get_table_names()) != original_tables:
        raise SystemExit("Schema is not the original six-table database; no changes made.")
    for name in original_tables:
        expected = set(Base.metadata.tables[name].columns.keys())
        if name == "consent_grants":
            expected -= {"allow_upload", "document_ids"}
        elif name == "patients":
            expected -= {"patient_code"}
        actual = {column["name"] for column in inspector.get_columns(name)}
        if actual != expected:
            raise SystemExit(f"Unexpected {name} schema; no changes made.")
    engine.dispose()
    folder = Path(backup_directory) if backup_directory else root / "backend" / "storage" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / ("legacy-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".db")
    with sqlite3.connect(url.database) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    config = Config(str(root / "backend" / "alembic.ini"))
    command.stamp(config, "0001")
    command.upgrade(config, "head")
    print(f"Legacy schema migrated; backup retained at {backup}. No clinical records were printed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup-directory", type=Path)
    adopt(parser.parse_args().backup_directory)

"""Create a private, non-deploying Vercel/Render/Supabase preparation directory."""

import hashlib
import json
import os
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def private_write(path, data):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def prepare():
    import app.models  # noqa: F401 -- collect only the application's registered tables
    from app.database import Base

    folder = ROOT / ".tools/hosting" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=False)
    render = (ROOT / "infra/hosting/render.env.example").read_text(encoding="utf-8")
    render = render.replace(
        "SECRET_KEY=\n", "SECRET_KEY=" + secrets.token_urlsafe(48) + "\n"
    )
    private_write(folder / "render.env", render.encode())
    private_write(
        folder / "vercel.env", (ROOT / "infra/hosting/vercel.env.example").read_bytes()
    )
    tables = sorted({*Base.metadata.tables, "alembic_version"})
    statements = [
        "-- Run only on the dedicated target project AFTER CareGap migrations.",
        "-- Direct table-owner backend connections remain usable; the Data API gets no app-table grants.",
        "BEGIN;",
    ]
    for table in tables:
        if not table.replace("_", "").isalnum():
            raise ValueError("Unsafe application table name")
        statements.extend(
            [
                f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;',
                f'REVOKE ALL ON TABLE public."{table}" FROM anon, authenticated;',
            ]
        )
    statements.append("COMMIT;")
    private_write(
        folder / "supabase_public_schema_lockdown.sql",
        ("\n".join(statements) + "\n").encode(),
    )
    manifest = {
        "mode": "preparation_only",
        "deployed": False,
        "data_transferred": False,
        "table_count": len(tables),
        "files": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()
        },
    }
    private_write(
        folder / "preparation-manifest.json",
        (json.dumps(manifest, indent=2) + "\n").encode(),
    )
    return {
        "preparation_directory": str(folder),
        "files_created": len(manifest["files"]) + 1,
        "secret_values_printed": False,
        "deployed": False,
        "data_transferred": False,
    }


if __name__ == "__main__":
    print(json.dumps(prepare()))

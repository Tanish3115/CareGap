"""Local database/vault backup. Never publishes data or prints secrets."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]


def command(args):
    result = subprocess.run(["docker", "compose", *args], cwd=root, capture_output=True, check=True)
    return result.stdout


if __name__ == "__main__":
    folder = (
        root / ".tools/backups" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    )
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "database.dump").write_bytes(
        command(["exec", "-T", "postgres", "pg_dump", "-U", "caregap_user", "-d", "caregap360_db", "-Fc"])
    )
    (folder / "local-vault.tar.gz").write_bytes(
        command(["exec", "-T", "backend", "tar", "-czf", "-", "-C", "/app/storage/documents", "."])
    )
    external_count = int(
        command(
            [
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "caregap_user",
                "-d",
                "caregap360_db",
                "-At",
                "-c",
                "SELECT count(*) FROM medical_documents WHERE storage_backend='s3'",
            ]
        ).strip()
    )
    manifest = dict(
        scope="database-and-local-vault",
        created_at=datetime.now(timezone.utc).isoformat(),
        files={file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in folder.iterdir()},
        s3_objects_need_separate_provider_snapshot=external_count,
        keys_and_environment_backed_up=False,
    )
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(backup_directory=str(folder), s3_objects_need_provider_snapshot=external_count)))

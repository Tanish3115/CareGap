"""Read-only local source inventory for a reviewed hosting cutover; no remote IO."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = """
import json
from sqlalchemy import text
from app.database import SessionLocal,Base
import app.models
from app.services.storage_service import storage_service
with SessionLocal() as db:
    schema=db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    counts={name:db.execute(text('SELECT COUNT(*) FROM "'+name+'"')).scalar_one() for name in Base.metadata.tables}
    sources=[dict(row) for row in db.execute(text('SELECT id,patient_id,file_path,storage_backend,sha256_hash,file_size FROM medical_documents ORDER BY id')).mappings()]
    for item in sources:
        if item['storage_backend']=='local':storage_service.get_secure_file_path(item['file_path'],item['sha256_hash'])
    active=db.execute(text("SELECT COUNT(*) FROM document_processing_jobs WHERE status IN ('queued','processing')")).scalar_one()
    pending=db.execute(text("SELECT COUNT(*) FROM file_deletions WHERE status='pending'")).scalar_one()
    print(json.dumps(dict(schema=schema,counts=counts,sources=sources,active_processing_jobs=active,pending_file_cleanup=pending)))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if not target.is_relative_to((ROOT / ".tools").resolve()):
        raise SystemExit("Keep the private inventory under ignored .tools")
    response = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "python", "-"],
        cwd=ROOT,
        input=CODE,
        text=True,
        capture_output=True,
        check=False,
    )
    if response.returncode:
        raise SystemExit(
            "Read-only inventory failed; private diagnostics were not printed"
        )
    inventory = json.loads(response.stdout)
    raw = (json.dumps(inventory, indent=2) + "\n").encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    print(
        json.dumps(
            {
                "inventory": str(target),
                "schema": inventory["schema"],
                "documents": len(inventory["sources"]),
                "local_source_checksums_verified": True,
                "active_processing_jobs": inventory["active_processing_jobs"],
                "pending_file_cleanup": inventory["pending_file_cleanup"],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "data_transferred": False,
            }
        )
    )


if __name__ == "__main__":
    main()

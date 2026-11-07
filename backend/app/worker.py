"""Local document worker: durable database leases and a supervised parser process."""

import argparse
import json
import signal
import subprocess
import sys
import os
import tempfile
from pathlib import Path
from threading import Event
from sqlalchemy.exc import SQLAlchemyError
from app.database import SessionLocal
import app.models  # noqa: F401 -- register every model before querying the durable queue
from app.models.document import MedicalDocument
from app.models.processing import DocumentProcessingJob
from app.schemas.processing import SourceTextResult
from app.services.document_processing import claim_job, finish_job


def execute_processor(key, checksum, storage_backend="local"):
    try:
        # Resolve the installed package explicitly. Safe-path mode keeps the
        # caller's cwd out of module lookup while preserving relative storage
        # configuration and .env resolution for the worker and its child.
        backend_dir = str(Path(__file__).resolve().parent.parent)
        with tempfile.TemporaryDirectory(prefix="caregap-process-") as folder:
            child = subprocess.run(
                [
                    sys.executable,
                    "-P",
                    "-m",
                    "app.document_processor",
                    "--key",
                    key,
                    "--sha256",
                    checksum,
                    "--storage-backend",
                    storage_backend,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=150,
                env={
                    **os.environ,
                    "TMPDIR": folder,
                    "TEMP": folder,
                    "TMP": folder,
                    "PYTHONPATH": backend_dir
                    + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""),
                },
            )
        if child.returncode:
            return None, "processing_failed"
        result = SourceTextResult.model_validate(json.loads(child.stdout))
        if result.source_sha256 != checksum:
            return None, "processing_failed"
        return result.model_dump(mode="json"), None
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception:
        return None, "processing_failed"


def run_one(session_factory=SessionLocal, executor=execute_processor):
    with session_factory() as db:
        claim = claim_job(db)
        if claim is None:
            return False
        job_id, token = claim
        job = db.get(DocumentProcessingJob, job_id)
        document = db.get(MedicalDocument, job.document_id)
        key, checksum, backend = document.file_path, document.sha256_hash, document.storage_backend
    result, error_code = executor(key, checksum, backend)
    with session_factory() as db:
        finish_job(db, job_id, token, result=result, error_code=error_code)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    if not 0.1 <= args.poll_seconds <= 30:
        parser.error("poll-seconds must be between 0.1 and 30")
    if args.once:
        run_one()
        return
    stopping = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    print("Document processing worker ready", flush=True)
    while not stopping.is_set():
        try:
            if run_one():
                continue
        except SQLAlchemyError:
            print("Document worker database unavailable; retrying", flush=True)
        stopping.wait(args.poll_seconds)


if __name__ == "__main__":
    main()

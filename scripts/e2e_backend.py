"""Isolated synthetic-only backend for browser tests; never opens the developer DB."""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
with tempfile.TemporaryDirectory(prefix="caregap-e2e-") as directory:
    os.environ.update(
        DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/test.db",
        STORAGE_DIR=str(Path(directory) / "documents"),
        ENVIRONMENT="test",
        SECRET_KEY="browser-test-secret-key-only-not-for-deployment",
        TERMINOLOGY_MODE="synthetic",
        SUMMARY_PROVIDER="extractive",
        SUMMARY_PROVIDER_APPROVED="false",
        STORAGE_BACKEND="local",
        RATE_LIMIT_STORAGE_URI="memory://",
        CORS_ORIGINS='["http://127.0.0.1:3100"]',
    )
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(root / "backend" / "alembic.ini")), "head")
    from app.database import SessionLocal
    from app.models.user import User
    from app.core.security import hash_password

    # Synthetic administrator exists only inside this disposable browser-test environment.
    with SessionLocal() as db:
        db.add(
            User(
                email="synthetic-admin@example.com",
                full_name="Synthetic E2E Administrator",
                role="admin",
                hashed_password=hash_password("SyntheticAdminBrowser123!"),
            )
        )
        db.commit()
    import uvicorn

    worker = subprocess.Popen(
        [sys.executable, "-m", "app.worker"],
        cwd=root / "backend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cleanup = subprocess.Popen(
        [sys.executable, "-m", "app.file_cleanup"],
        cwd=root / "backend",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8100, access_log=False)
    finally:
        cleanup.terminate()
        try:
            cleanup.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cleanup.kill()
            cleanup.wait()
        worker.terminate()
        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()

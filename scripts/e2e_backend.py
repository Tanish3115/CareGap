"""Isolated synthetic-only backend for browser tests; never opens the developer DB."""
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
with tempfile.TemporaryDirectory(prefix="caregap-e2e-") as directory:
    os.environ.update(DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/test.db",
                      STORAGE_DIR=str(Path(directory) / "documents"), ENVIRONMENT="test",
                      SECRET_KEY="browser-test-secret-key-only-not-for-deployment",
                      CORS_ORIGINS='["http://127.0.0.1:3100"]')
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(root / "backend" / "alembic.ini")), "head")
    from app.database import SessionLocal
    from app.models.user import User
    from app.core.security import hash_password
    # Synthetic administrator exists only inside this disposable browser-test environment.
    with SessionLocal() as db:
        db.add(User(email="synthetic-admin@example.com", full_name="Synthetic E2E Administrator", role="admin",
                    hashed_password=hash_password("SyntheticAdminBrowser123!")))
        db.commit()
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8100)

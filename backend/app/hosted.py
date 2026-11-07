"""Persistent Render service supervisor. Never resets the configured database or vault."""

import os
import signal
import subprocess
import sys
from threading import Event
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url


def validate_hosted(settings):
    url = make_url(settings.DATABASE_URL)
    if url.drivername != "postgresql+psycopg" or url.query.get("sslmode") not in {
        "require",
        "verify-ca",
        "verify-full",
    }:
        raise ValueError("Hosted database requires psycopg PostgreSQL and explicit TLS")
    if settings.STORAGE_BACKEND != "s3" or not settings.COOKIE_SECURE or settings.DEMO_MODE:
        raise ValueError(
            "Persistent hosting requires private object storage, secure cookies and demo mode disabled"
        )
    if not settings.CORS_ORIGINS:
        raise ValueError("Specify the exact frontend origin")
    for origin in settings.CORS_ORIGINS:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or "*" in origin
        ):
            raise ValueError("Hosted frontend origins must be explicit HTTPS origins")


def main():
    from app.config import settings

    validate_hosted(settings)
    port = int(os.environ.get("PORT", "10000"))
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid hosted port")
    migrated = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True)
    if migrated.returncode:
        raise RuntimeError("Hosted migration failed; database details were not printed")
    stopping = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    processes = []
    try:
        commands = [
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
                "--no-access-log",
                "--no-proxy-headers",
            ],
            [sys.executable, "-m", "app.worker"],
            [sys.executable, "-m", "app.file_cleanup"],
        ]
        for command in commands:
            processes.append(subprocess.Popen(command))
        while not stopping.wait(1):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A hosted process exited; restart required")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()

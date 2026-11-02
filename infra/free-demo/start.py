"""One-container disposable demo. Never mounts or migrates an existing database."""

import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
from threading import Event
import time
from urllib.parse import urlsplit
import urllib.request


def demo_environment(source, directory):
    origin = source.get("RENDER_EXTERNAL_URL") or source.get("CAREGAP_DEMO_ORIGIN", "")
    parsed = urlsplit(origin)
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
    ):
        raise ValueError("Set an HTTPS demo origin, or an explicit loopback test origin")
    port = int(source.get("PORT", "10000"))
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid demo port")
    # All external processors/transports stay off regardless of host environment values.
    env = dict(source)
    env.update(
        DATABASE_URL="sqlite:///" + (directory / "demo.db").as_posix(),
        STORAGE_DIR=str(directory / "documents"),
        SECRET_KEY=secrets.token_urlsafe(48),
        ENVIRONMENT="development",
        DEMO_MODE="true",
        COOKIE_SECURE="false" if local and parsed.scheme == "http" else "true",
        CORS_ORIGINS=json.dumps([origin.rstrip("/")]),
        STORAGE_BACKEND="local",
        S3_ACCESS_KEY_ID="",
        S3_SECRET_ACCESS_KEY="",
        SUMMARY_PROVIDER="extractive",
        SUMMARY_PROVIDER_APPROVED="false",
        SUMMARY_PROVIDER_TOKEN="",
        TERMINOLOGY_MODE="disabled",
        KNOWLEDGE_MODE="disabled",
        RATE_LIMIT_STORAGE_URI="memory://",
        PORT=str(port),
        HOSTNAME="0.0.0.0",
        API_PROXY_TARGET="http://127.0.0.1:8000",
    )
    return env


def main():
    stopping = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopping.set())
    backend = Path("/opt/caregap/backend")
    processes = []
    with tempfile.TemporaryDirectory(prefix="caregap-disposable-demo-") as directory:
        env = demo_environment(os.environ, Path(directory))
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=backend, env=env, check=True)
        try:
            for command in (
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--no-access-log",
                    "--proxy-headers",
                    "--forwarded-allow-ips",
                    "127.0.0.1",
                ],
                [sys.executable, "-m", "app.worker"],
                [sys.executable, "-m", "app.file_cleanup"],
            ):
                processes.append(subprocess.Popen(command, cwd=backend, env=env))
            ready = False
            for _ in range(120):
                if stopping.is_set() or any(item.poll() is not None for item in processes):
                    break
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8000/ready", timeout=1) as response:
                        ready = response.status == 200
                    if ready:
                        break
                except OSError:
                    pass
                stopping.wait(0.25)
            if not ready:
                raise RuntimeError("Demo API did not become ready")
            processes.append(subprocess.Popen(["node", "server.js"], cwd="/opt/caregap/frontend", env=env))
            print("Disposable synthetic-only demo ready; data resets on restart", flush=True)
            while not stopping.wait(1):
                if any(item.poll() is not None for item in processes):
                    raise RuntimeError("A demo process exited")
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
            deadline = time.monotonic() + 15
            for process in processes:
                try:
                    process.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()

"""Package source, tests and docs only; exclude runtime data and private settings."""

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ("README.md", "docker-compose.yml", ".env.example", ".gitignore", ".dockerignore", "render.yaml")
DIRECTORIES = {
    "backend/app": {".py", ".json"},
    "backend/tests": {".py"},
    "backend/migrations": {".py"},
    "frontend/src": {".ts", ".tsx", ".css", ".json"},
    "frontend/tests": {".ts"},
    "docs": {".md"},
    "scripts": {".py", ".cjs", ".mjs"},
    "research": {".py", ".md", ".in", ".txt", ".json"},
    ".github/workflows": {".yml", ".yaml"},
    "infra": {".yml", ".yaml", ".md", ".sh", ".py"},
}
EXTRA = (
    "backend/alembic.ini",
    "backend/pyproject.toml",
    "backend/Dockerfile",
    "backend/.dockerignore",
    "backend/.env.example",
    "backend/requirements.txt",
    "backend/requirements-dev.lock.txt",
    "backend/requirements.lock.txt",
    "backend/storage/documents/.gitkeep",
    "frontend/Dockerfile",
    "frontend/.dockerignore",
    "frontend/AGENTS.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vercel.json",
    "frontend/tsconfig.json",
    "frontend/next.config.mjs",
    "frontend/next-env.d.ts",
    "frontend/postcss.config.mjs",
    "frontend/postcss.config.js",
    "frontend/tailwind.config.ts",
    "frontend/tailwind.config.js",
    "frontend/biome.json",
    "frontend/playwright.config.ts",
    "infra/minio/Dockerfile",
    "infra/staging/Caddyfile",
    "infra/free-demo/Dockerfile",
    "infra/hosting/render.env.example",
    "infra/hosting/vercel.env.example",
)


def package():
    paths = {ROOT / path for path in (*ROOT_FILES, *EXTRA) if (ROOT / path).is_file()}
    for directory, extensions in DIRECTORIES.items():
        paths.update(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file()
            and path.suffix in extensions
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
        )
    private_values = []
    for env_path in (ROOT / ".env", ROOT / "backend/.env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                value = value.strip().strip("\"'")
                if separator and re.search(r"SECRET|PASSWORD|TOKEN|ACCESS_KEY", key) and len(value) >= 16:
                    private_values.append(value.encode())
    contents = {}
    for path in sorted(paths):
        if not path.resolve().is_relative_to(ROOT) or path.is_symlink():
            raise RuntimeError("Source package contains an unsupported linked path")
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        if relative.startswith("backend/app/data/"):
            approved = {"synthetic_risk.json", "synthetic_models.json", "synthetic_interventions.json"}
            if path.name not in approved or json.loads(data).get("mode") != "synthetic_only":
                raise RuntimeError("Unreviewed application data artifact blocks source packaging")
        if any(value in data for value in private_values) or re.search(
            rb"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----", data
        ):
            raise RuntimeError("Configured private value found in source file: " + relative)
        contents[relative] = data
    # Docker's optional offline-wheel COPY still needs an empty directory on fresh installs.
    contents.setdefault("backend/wheelhouse/.gitkeep", b"")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / ".tools/handover"
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f"CareGap-360-source-{stamp}.zip"
    manifest = dict(
        created_at_utc=stamp,
        scope="source-tests-documentation",
        excluded=[
            "private environment files",
            "patient files",
            "databases",
            "backups",
            "dependencies",
            "build artifacts",
            "Git history",
        ],
        files={name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    )
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for name, data in contents.items():
            output.writestr(name, data)
        output.writestr("HANDOVER_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(output.read(name)).hexdigest() == expected
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", encoding="utf-8")
    return dict(archive=str(archive), source_files=len(contents), sha256=digest, verified=True)


if __name__ == "__main__":
    print(json.dumps(package()))

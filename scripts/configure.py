"""Generate local development secrets without overwriting existing configuration."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for target, content in [
    (
        root / ".env",
        f"SECRET_KEY={secrets.token_urlsafe(48)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n",
    ),
    (
        root / "backend" / ".env",
        f"SECRET_KEY={secrets.token_urlsafe(48)}\nENVIRONMENT=development\nDATABASE_URL=sqlite:///./caregap360.db\n",
    ),
]:
    if target.exists():
        print(f"Keeping existing {target.relative_to(root)}")
    else:
        target.write_text(content, encoding="utf-8")
        print(f"Created {target.relative_to(root)} (secrets omitted)")

# Optional local object-storage credentials; add only missing keys, never rotate existing secrets.
target = root / ".env"
existing = target.read_text(encoding="utf-8")
known = {line.split("=", 1)[0] for line in existing.splitlines() if "=" in line and not line.startswith("#")}
additions = []
for name, value in (
    ("MINIO_ROOT_USER", "caregap-" + secrets.token_hex(6)),
    ("MINIO_ROOT_PASSWORD", secrets.token_urlsafe(36)),
):
    if name not in known:
        additions.append(f"{name}={value}")
if additions:
    with target.open("a", encoding="utf-8") as output:
        output.write("\n" + "\n".join(additions) + "\n")
    print("Added missing optional local object-storage credentials (values omitted)")

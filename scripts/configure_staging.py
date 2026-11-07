"""Generate isolated local-rehearsal secrets only if missing; never prints values."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".tools/staging.env"
target.parent.mkdir(exist_ok=True)
if not target.exists():
    target.write_text(
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(36)}\nSECRET_KEY={secrets.token_urlsafe(48)}\nSTORAGE_BACKEND=local\n",
        encoding="utf-8",
    )
print(f"Local rehearsal configuration: {target}")

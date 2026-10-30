"""Generate local development secrets without overwriting existing configuration."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for target, content in [
    (root / ".env", f"SECRET_KEY={secrets.token_urlsafe(48)}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"),
    (root / "backend" / ".env", f"SECRET_KEY={secrets.token_urlsafe(48)}\nENVIRONMENT=development\nDATABASE_URL=sqlite:///./caregap360.db\n"),
]:
    if target.exists():
        print(f"Keeping existing {target.relative_to(root)}")
    else:
        target.write_text(content, encoding="utf-8")
        print(f"Created {target.relative_to(root)} (secrets omitted)")

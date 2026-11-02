"""Explicitly create a private development bucket. Never grants anonymous access."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.storage_admin import main

if __name__ == "__main__":
    main()

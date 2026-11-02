"""Generate the versioned, synthetic-only model artifact; no patient database access."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.services.synthetic_risk import evaluate

if __name__ == "__main__":
    result = evaluate()
    target = root / "backend/app/data/synthetic_risk.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(mode=result["mode"], test=result["test"], artifact=str(target)), indent=2))
